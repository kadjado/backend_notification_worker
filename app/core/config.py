from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "SCDIP - PNLP"

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Refresh tokens
    refresh_token_expire_days: int = 30
    refresh_cookie_name: str = "scdip_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"

    # Meta WhatsApp
    meta_whatsapp_access_token: str | None = None
    meta_whatsapp_phone_number_id: str | None = None
    meta_whatsapp_graph_api_version: str = "v23.0"
    meta_whatsapp_template_name: str | None = None
    meta_whatsapp_template_language: str = "fr"
    meta_whatsapp_verify_token: str | None = None
    meta_whatsapp_app_secret: str | None = None

    # Firebase Cloud Messaging
    firebase_service_account_path: Path = (
        BASE_DIR / "secrets" / "firebase-service-account.json"
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )


settings = Settings()