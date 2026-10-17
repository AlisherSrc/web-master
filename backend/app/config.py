"""Application configuration, loaded exclusively from environment variables.

Nothing secret is hard-coded here — Docker Compose injects the values from the
git-ignored `.env` file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    app_name: str = "Celestial Classifier"

    # --- Database -----------------------------------------------------------
    postgres_user: str
    postgres_password: str = Field(repr=False)
    postgres_db: str
    db_host: str = "db"
    db_port: int = 5432

    # --- Classifier ---------------------------------------------------------
    classifier_mode: Literal["auto", "gemini", "mock"] = "auto"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"

    # --- Misc ---------------------------------------------------------------
    max_upload_mb: int = Field(default=5, ge=1, le=20)
    log_level: str = "info"

    @property
    def database_url(self) -> URL:
        # URL.create safely escapes special characters in the password.
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
