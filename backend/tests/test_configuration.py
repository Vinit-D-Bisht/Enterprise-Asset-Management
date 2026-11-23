import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_local_token_placeholder():
    with pytest.raises(ValidationError, match="unique JWT_SECRET_KEY"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://user:password@db:5432/eamms",
            JWT_SECRET_KEY="local-dev-only-change-this-random-secret-before-deployment",
            APP_ENV="production",
            COOKIE_SECURE=True,
            CORS_ORIGINS="https://eamms.example.com",
        )


def test_production_accepts_secure_database_cookie_and_origins():
    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://user:password@db:5432/eamms",
        JWT_SECRET_KEY="a-unique-production-secret-with-more-than-32-characters",
        APP_ENV="production",
        COOKIE_SECURE=True,
        CORS_ORIGINS="https://eamms.example.com",
    )
    assert config.cors_origin_list == ["https://eamms.example.com"]
