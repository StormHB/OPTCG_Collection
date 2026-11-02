from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Datoteka je u api/app/core/, a .env na razini repozitorija.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "One Piece TCG Collection API"
    ENV: str = "dev"
    DATABASE_URL: str
    JWT_SECRET: str = "dev-only-placeholder"

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


settings = Settings()
