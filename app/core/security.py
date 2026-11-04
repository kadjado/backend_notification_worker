import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hache un mot de passe avant son enregistrement."""
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe sans le stocker en clair."""
    return password_hash.verify(password, hashed_password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """Crée un jeton JWT associé à un utilisateur."""
    now = datetime.now(timezone.utc)
    duration = expires_delta or timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + duration,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Vérifie le jeton JWT et renvoie ses données."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp"]},
    )


def create_refresh_token() -> str:
    """Génère un refresh token cryptographiquement aléatoire."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Retourne le hash SHA-256 d'un refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()