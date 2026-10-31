from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_schemas import (
    AuthenticatedUser,
    LoginRequest,
    LoginResponse,
)
from app.db.dependencies import get_db
from app.core.security import verify_password, create_access_token
from app.models import Utilisateur


router = APIRouter(prefix="/api/v1/auth", tags=["Authentification"])


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
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

    token = create_access_token(str(utilisateur.id))

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=AuthenticatedUser(
            id=utilisateur.id,
            nom=utilisateur.nom,
            prenom=utilisateur.prenom,
            email=utilisateur.email,
            role=utilisateur.role,
        ),
    )

from app.core.dependencies import get_current_user

@router.get("/me", response_model=AuthenticatedUser)
def get_me(
    current_user: Utilisateur = Depends(get_current_user),
) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=current_user.id,
        nom=current_user.nom,
        prenom=current_user.prenom,
        email=current_user.email,
        role=current_user.role,
    )