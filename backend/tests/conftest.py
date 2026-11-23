from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database.session import Base, get_db
from app.main import app
from app.models import Role, User


@pytest.fixture
def database() -> Generator[sessionmaker, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        yield TestingSession
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def users(database):
    records = {}
    with database() as db:
        for role in Role:
            email = f"{role.value.replace('_', '.')}@example.com"
            user = User(
                full_name=role.value.replace("_", " ").title(),
                email=email,
                normalized_email=email,
                password_hash=hash_password("correct-horse-battery-staple"),
                role=role.value,
                is_active=True,
            )
            db.add(user)
            records[role.value] = user
        db.commit()
        for user in records.values():
            db.refresh(user)
        records = {role: user.id for role, user in records.items()}
    return records


@pytest.fixture
def client(database):
    def override_get_db():
        with database() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(users):
    return {
        role: {"Authorization": f"Bearer {create_access_token(user_id)}"}
        for role, user_id in users.items()
    }


@pytest.fixture
def basic_asset(client, auth_headers):
    headers = auth_headers[Role.ASSET_MANAGER.value]
    category = client.post(
        "/api/v1/categories", headers=headers, json={"name": "Computers"}
    )
    location = client.post(
        "/api/v1/locations", headers=headers, json={"name": "HQ", "code": "HQ"}
    )
    assert category.status_code == 201
    assert location.status_code == 201
    response = client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "asset_tag": "LAP-001",
            "name": "Engineering laptop",
            "category_id": category.json()["id"],
            "location_id": location.json()["id"],
            "purchase_date": "2024-01-01",
            "purchase_cost": "1200.00",
            "residual_value": "200.00",
            "useful_life_months": 60,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
