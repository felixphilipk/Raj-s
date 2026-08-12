from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://drivebook:drivebook@localhost:5432/drivebook"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 10080
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    payments_mode: str = "demo"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    smtp_mode: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@example.com"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
