from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "NIT OA system"
    environment: str = "development"
    secret_key: str = "change-this-dev-secret"
    access_token_expire_minutes: int = 15
    frontend_url: str = "http://localhost:8080"
    backend_cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"

    database_url: str = "mysql+pymysql://admin:admin123@127.0.0.1:3306/oa"
    redis_url: str = "redis://127.0.0.1:6379/0"

    app_admin_email: str = "admin@example.com"
    app_admin_password: str = "admin123"
    default_employee_password: str = "ChangeMe123!"
    password_reset_email_enabled: bool = False

    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.5"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    smtp_use_tls: bool = True
    hr_reminder_email: str = "hr@nit-g.co.jp"

    mailbox_poll_enabled: bool = False
    mailbox_poll_interval_seconds: int = 60
    mailbox_imap_host: str = ""
    mailbox_imap_username: str = ""
    mailbox_imap_password: str = ""
    mailbox_imap_folder: str = "INBOX"

    dify_assistant_enabled: bool = False
    dify_assistant_api_base: str = ""
    dify_assistant_api_key: str = ""
    dify_assistant_app_url: str = ""
    dify_assistant_title: str = "NIT AI Assistant"
    dify_assistant_greeting: str = "会社情報や手続きについて質問できます。"
    dify_assistant_default_inputs: str = "{}"
    dify_assistant_response_mode: str = "blocking"
    dify_assistant_timeout_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.backend_cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
