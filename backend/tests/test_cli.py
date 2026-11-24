import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import cli
from app.core.security import verify_password
from app.database.session import Base
from app.models import AuditLog, Role, User


def test_create_admin_cli_creates_bootstrap_account(monkeypatch, capsys):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(cli, "SessionLocal", TestSession)
    passwords = iter(["a-secure-password-123", "a-secure-password-123"])
    monkeypatch.setattr(cli, "getpass", lambda _prompt: next(passwords))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.cli",
            "create-admin",
            "--email",
            "Admin@Example.com",
            "--name",
            "System Administrator",
        ],
    )

    try:
        cli.main()
        with TestSession() as db:
            user = db.scalar(select(User))
            event = db.scalar(select(AuditLog))
            assert user is not None
            assert user.email == "admin@example.com"
            assert user.role == Role.ADMINISTRATOR.value
            assert verify_password("a-secure-password-123", user.password_hash)
            assert event is not None and event.action == "user.bootstrap_admin"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
