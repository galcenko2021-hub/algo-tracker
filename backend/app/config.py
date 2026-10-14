from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    environment: Literal["dev", "prod"] = "dev"
    secret_key: str = Field(default="dev-secret-change-me-0123456789abcdef", min_length=8)
    database_url: str = "postgresql+psycopg://algo:algo@localhost:5432/algo"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cf_base_url: str = "https://codeforces.com/api"
    cf_min_interval_seconds: float = 2.0
    rate_limit_enabled: bool = True

    @model_validator(mode="after")
    def _require_real_secret_in_prod(self) -> "Settings":
        if self.environment == "prod" and self.secret_key.startswith(("dev-secret", "change-me")):
            raise ValueError("SECRET_KEY must be set to a random value when ENVIRONMENT=prod")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.environment != "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
