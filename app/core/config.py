
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "SCDIP - PNLP"
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

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
