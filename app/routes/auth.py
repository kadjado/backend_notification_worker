from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth_schemas import (
    AuthenticatedUser,
    LoginRequest,
    LoginResponse,
    TokenRefreshResponse,
)
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.db.dependencies import get_db
from app.models import RefreshToken, Utilisateur


router = APIRouter(prefix="/api/v1/auth", tags=["Authentification"])


def set_refresh_cookie(response: Response, token: str) -> None:
    """Place le refresh token dans un cookie HttpOnly."""
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    """Supprime le cookie de renouvellement."""
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth",
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


def create_refresh_token_record(
    db: Session,
    utilisateur_id: int,
) -> str:
    """Crée un refresh token et stocke uniquement son hash."""
    raw_token = create_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    db.add(
        RefreshToken(
            utilisateur_id=utilisateur_id,
            token_hash=token_hash,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=settings.refresh_token_expire_days)
            ),
        )
    )

    return raw_token


def user_response(utilisateur: Utilisateur) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=utilisateur.id,
        nom=utilisateur.nom,
        prenom=utilisateur.prenom,
        email=utilisateur.email,
        role=utilisateur.role,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    email = data.email.strip().lower()

    utilisateur = db.scalar(
        select(Utilisateur).where(Utilisateur.email == email)
    )

    if utilisateur is None or not verify_password(
        data.password,
        utilisateur.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not utilisateur.actif:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé. Contactez votre administrateur.",
        )

    refresh_token = create_refresh_token_record(db, utilisateur.id)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    set_refresh_cookie(response, refresh_token)

    return LoginResponse(
        access_token=create_access_token(str(utilisateur.id)),
        token_type="bearer",
        user=user_response(utilisateur),
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_access_token(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=settings.refresh_cookie_name,
    ),
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    if not refresh_token:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée. Veuillez vous reconnecter.",
        )

    token_hash = hash_refresh_token(refresh_token)

    stored_token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )

    if stored_token is None:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide.",
        )

    now = datetime.now(timezone.utc)

    if stored_token.revoque_le is not None:
        # Réutilisation d'un ancien refresh token :
        # révocation de toutes les sessions de cet utilisateur.
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.utilisateur_id == stored_token.utilisateur_id,
                RefreshToken.revoque_le.is_(None),
            )
            .values(revoque_le=now)
        )
        db.commit()
        clear_refresh_cookie(response)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session révoquée. Veuillez vous reconnecter.",
        )

    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        stored_token.revoque_le = now
        db.commit()
        clear_refresh_cookie(response)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expiré. Veuillez vous reconnecter.",
        )

    utilisateur = db.get(Utilisateur, stored_token.utilisateur_id)

    if utilisateur is None or not utilisateur.actif:
        stored_token.revoque_le = now
        db.commit()
        clear_refresh_cookie(response)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte indisponible. Veuillez vous reconnecter.",
        )

    new_refresh_token = create_refresh_token_record(db, utilisateur.id)
    new_refresh_hash = hash_refresh_token(new_refresh_token)

    stored_token.revoque_le = now
    stored_token.remplace_par_hash = new_refresh_hash

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    set_refresh_cookie(response, new_refresh_token)

    return TokenRefreshResponse(
        access_token=create_access_token(str(utilisateur.id)),
        token_type="bearer",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=settings.refresh_cookie_name,
    ),
    db: Session = Depends(get_db),
) -> Response:
    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)

        stored_token = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash
            )
        )

        if stored_token is not None and stored_token.revoque_le is None:
            stored_token.revoque_le = datetime.now(timezone.utc)
            db.commit()

    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthenticatedUser)
def get_me(
    current_user: Utilisateur = Depends(get_current_user),
) -> AuthenticatedUser:
    return user_response(current_user)