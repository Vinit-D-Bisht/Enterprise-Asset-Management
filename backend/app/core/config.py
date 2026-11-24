from functools import lru_cache
from pathlib import Path

import pycountry
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ACCESS_MINUTES: int = Field(default=15, ge=1, le=60)
    JWT_REFRESH_DAYS: int = Field(default=7, ge=1, le=30)
    COMPANY_CURRENCY: str = Field(default="INR", pattern="^[A-Z]{3}$")
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    COOKIE_SECURE: bool = False
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("COMPANY_CURRENCY")
    @classmethod
    def validate_iso_4217_currency(cls, value: str) -> str:
        if pycountry.currencies.get(alpha_3=value) is None:
            raise ValueError("COMPANY_CURRENCY must be an ISO 4217 currency code")
        return value

    @model_validator(mode="after")
    def enforce_production_settings(self):
        if self.APP_ENV.lower() == "production":
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be enabled in production")
            if not self.DATABASE_URL.startswith(
                ("postgresql://", "postgresql+", "postgres://")
            ):
                raise ValueError("Production requires PostgreSQL")
            if (
                "local-dev-only" in self.JWT_SECRET_KEY.lower()
                or "change-this" in self.JWT_SECRET_KEY.lower()
            ):
                raise ValueError("Production requires a unique JWT_SECRET_KEY")
            if any(
                not origin.startswith("https://") for origin in self.cors_origin_list
            ):
                raise ValueError("Production CORS origins must use HTTPS")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
