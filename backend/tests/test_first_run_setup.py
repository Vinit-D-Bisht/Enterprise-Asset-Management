from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, verify_password
from app.database.session import Base, get_db
from app.main import app
from app.models import (
    Asset,
    AssetCategory,
    Assignment,
    AuditLog,
    Department,
    Location,
    MaintenancePlan,
    Notification,
    Role,
    Transfer,
    User,
    Vendor,
    Warranty,
    WorkOrder,
)
from app.services import setup as setup_service


def payload(**changes):
    data = {
        "full_name": "  Meera Krishnan ",
        "email": "Meera.Krishnan@example.com",
        "password": "a-unique-secure-password-42",
        "confirm_password": "a-unique-secure-password-42",
        "sample_data": False,
    }
    data.update(changes)
    return data


@pytest.fixture
def isolated_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    from fastapi.testclient import TestClient

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def count(factory, model):
    with factory() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_fresh_database_reports_setup_required(isolated_client):
    client, _ = isolated_client
    response = client.get("/api/v1/setup/status")
    assert response.status_code == 200
    assert response.json() == {"setup_required": True}


def test_existing_administrator_disables_setup(isolated_client):
    client, factory = isolated_client
    with factory() as db:
        db.add(
            User(
                full_name="Existing Admin",
                email="old@example.com",
                normalized_email="old@example.com",
                password_hash=hash_password("an-existing-secret-password"),
                role=Role.ADMINISTRATOR.value,
                is_active=True,
            )
        )
        db.commit()
    assert client.get("/api/v1/setup/status").json()["setup_required"] is False
    response = client.post("/api/v1/setup/initial-admin", json=payload())
    assert response.status_code == 409
    assert count(factory, User) == 1


def test_successful_admin_creation_uses_argon2_and_audit(isolated_client):
    client, factory = isolated_client
    response = client.post("/api/v1/setup/initial-admin", json=payload())
    assert response.status_code == 201, response.text
    user = response.json()["administrator"]
    assert user["email"] == "meera.krishnan@example.com"
    with factory() as db:
        saved = db.get(User, UUID(user["id"]))
        assert saved.role == "administrator" and saved.is_active
        assert saved.full_name == "Meera Krishnan"
        assert saved.password_hash.startswith("$argon2id$")
        assert verify_password(payload()["password"], saved.password_hash)
        assert db.scalar(
            select(AuditLog).where(AuditLog.action == "user.bootstrap_admin")
        )


def test_sample_data_disabled_creates_only_admin(isolated_client):
    client, factory = isolated_client
    response = client.post("/api/v1/setup/initial-admin", json=payload())
    assert response.status_code == 201, response.text
    assert response.json()["sample_data_created"] is False
    for model in (
        Department,
        Location,
        AssetCategory,
        Vendor,
        Asset,
        Assignment,
        MaintenancePlan,
        WorkOrder,
        Warranty,
        Transfer,
        Notification,
    ):
        assert count(factory, model) == 0, model.__name__


def test_sample_data_relationships_and_foreign_keys(isolated_client):
    client, factory = isolated_client
    response = client.post(
        "/api/v1/setup/initial-admin", json=payload(sample_data=True)
    )
    assert response.status_code == 201, response.text
    assert response.json()["sample_data_created"] is True
    with factory() as db:
        assert db.scalar(select(func.count(Department.id))) == 4
        assert db.scalar(select(func.count(Location.id))) == 3
        assert db.scalar(select(func.count(AssetCategory.id))) == 3
        assert db.scalar(select(func.count(Vendor.id))) == 3
        assert db.scalar(select(func.count(Asset.id))) == 6
        assert db.scalar(select(func.count(Assignment.id))) == 3
        assert db.scalar(select(func.count(MaintenancePlan.id))) == 1
        assert db.scalar(select(func.count(WorkOrder.id))) == 2
        assert db.scalar(select(func.count(Warranty.id))) == 4
        assert db.scalar(select(func.count(Transfer.id))) == 1
        assert db.scalar(select(func.count(Notification.id))) == 3
        assert all(user.department_id for user in db.scalars(select(User)).all())
        for asset in db.scalars(select(Asset)).all():
            assert db.get(AssetCategory, asset.category_id)
            assert db.get(Location, asset.location_id)
            assert db.get(Vendor, asset.vendor_id)
        for row in db.scalars(select(Assignment)).all():
            assert (
                db.get(Asset, row.asset_id)
                and db.get(User, row.user_id)
                and db.get(User, row.assigned_by_id)
            )
        for order in db.scalars(select(WorkOrder)).all():
            assert db.get(Asset, order.asset_id) and db.get(User, order.requested_by_id)
        for warranty in db.scalars(select(Warranty)).all():
            assert db.get(Asset, warranty.asset_id) and db.get(
                Vendor, warranty.vendor_id
            )
        for transfer in db.scalars(select(Transfer)).all():
            assert db.get(Asset, transfer.asset_id)
            assert db.get(Location, transfer.from_location_id) and db.get(
                Location, transfer.to_location_id
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "not-an-email"},
        {"password": "short", "confirm_password": "short"},
        {
            "password": "a-secure-password-123",
            "confirm_password": "a-different-password-123",
        },
        {"full_name": "  "},
    ],
)
def test_invalid_setup_input_rejected_without_records(isolated_client, changes):
    client, factory = isolated_client
    response = client.post("/api/v1/setup/initial-admin", json=payload(**changes))
    assert response.status_code == 422
    assert count(factory, User) == 0


def test_setup_cannot_be_repeated(isolated_client):
    client, factory = isolated_client
    assert client.post("/api/v1/setup/initial-admin", json=payload()).status_code == 201
    assert (
        client.post(
            "/api/v1/setup/initial-admin", json=payload(email="second@example.com")
        ).status_code
        == 409
    )
    assert count(factory, User) == 1


def test_sample_data_failure_rolls_back_every_record(isolated_client, monkeypatch):
    client, factory = isolated_client

    def fail_after_sample(db, admin):
        db.add(Department(name="Must roll back"))
        db.flush()
        raise RuntimeError("forced setup failure")

    monkeypatch.setattr(setup_service, "_sample_data", fail_after_sample)
    response = client.post(
        "/api/v1/setup/initial-admin", json=payload(sample_data=True)
    )
    assert response.status_code == 500
    for model in (User, Department, AuditLog):
        assert count(factory, model) == 0


def test_concurrent_setup_submissions_create_one_admin():
    with NamedTemporaryFile(
        prefix="eamms-setup-test-", suffix=".sqlite", delete=False
    ) as database_file:
        database_path = Path(database_file.name)
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 20},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.schemas.setup import InitialSetupRequest

    requests = [
        InitialSetupRequest(**payload(email=f"admin{index}@example.com"))
        for index in range(2)
    ]

    def create(data):
        with factory() as db:
            try:
                setup_service.initialize(db, data)
                return "created"
            except HTTPException as exc:
                return exc.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, requests))
        assert results.count("created") == 1
        assert results.count(409) == 1
        assert count(factory, User) == 1
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        database_path.unlink(missing_ok=True)
