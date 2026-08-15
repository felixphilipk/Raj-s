from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = ""
    postgres_url: str = ""
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 10080
    frontend_url: str = ""
    cors_origins: str = ""
    vercel_url: str = ""
    payments_mode: str = "demo"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    smtp_mode: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@example.com"
    smtp_use_tls: bool = True
    reminder_secret: str = ""
    reminder_hours_before: int = 24
    feedback_reminder_minutes_after: int = 30
    booking_hold_minutes: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def normalize_runtime_urls(self):
        url = self.database_url or self.postgres_url or "postgresql+psycopg://drivebook:drivebook@localhost:5432/drivebook"
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgres://")
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        self.database_url = url
        if not self.frontend_url:
            self.frontend_url = f"https://{self.vercel_url}" if self.vercel_url else "http://localhost:3000"
        if not self.cors_origins:
            self.cors_origins = self.frontend_url
        return self

settings = Settings()
