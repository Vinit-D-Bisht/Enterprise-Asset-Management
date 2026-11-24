import argparse
from getpass import getpass

from sqlalchemy import select, text

from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models import Role, User
from app.schemas.auth import UserCreate
from app.services.audit import record_audit


def create_admin(email: str, full_name: str) -> None:
    password = getpass("Administrator password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    data = UserCreate(
        full_name=full_name,
        email=email,
        password=password,
        role=Role.ADMINISTRATOR.value,
    )
    normalized_email = str(data.email).strip().lower()
    with SessionLocal() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": 704891226551129923},
            )
        if db.scalar(select(User.id).where(User.role == Role.ADMINISTRATOR.value)):
            raise SystemExit("An administrator already exists")
        user = User(
            full_name=data.full_name,
            email=normalized_email,
            normalized_email=normalized_email,
            password_hash=hash_password(password),
            role=Role.ADMINISTRATOR.value,
            is_active=True,
        )
        db.add(user)
        db.flush()
        record_audit(db, None, "user.bootstrap_admin", "user", user.id)
        db.commit()
    print(f"Administrator account created for {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="EAMMS administration commands")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create-admin", help="Create the initial administrator"
    )
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name)


if __name__ == "__main__":
    main()
