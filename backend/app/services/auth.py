from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshSession, Role, User
from app.schemas.auth import LoginInput, UserCreate
from app.services.audit import record_audit


def authenticate(db: Session, credentials: LoginInput) -> tuple[User, str]:
    normalized_email = str(credentials.email).strip().lower()
    user = db.scalar(select(User).where(User.normalized_email == normalized_email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    raw_token = create_refresh_token()
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.JWT_REFRESH_DAYS),
        )
    )
    record_audit(db, user.id, "auth.login", "user", user.id)
    db.commit()
    return user, raw_token


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str]:
    token_hash = hash_refresh_token(raw_token)
    stored = db.scalar(
        select(RefreshSession)
        .where(RefreshSession.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if stored is None:
        db.rollback()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        )
    if stored.revoked_at is not None:
        # A rotated token replay means the token may have been stolen. Revoke
        # every token in its family so the legitimate browser must log in again.
        family = db.scalars(
            select(RefreshSession)
            .where(RefreshSession.family_id == stored.family_id)
            .with_for_update()
        ).all()
        for session in family:
            if session.revoked_at is None:
                session.revoked_at = now
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected; sign in again"
        )
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        stored.revoked_at = now
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        )
    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        stored.revoked_at = now
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        )
    replacement = create_refresh_token()
    replacement_hash = hash_refresh_token(replacement)
    stored.revoked_at = now
    stored.replaced_by_hash = replacement_hash
    db.add(
        RefreshSession(
            user_id=user.id,
            family_id=stored.family_id,
            token_hash=replacement_hash,
            expires_at=now + timedelta(days=settings.JWT_REFRESH_DAYS),
        )
    )
    record_audit(db, user.id, "auth.refresh", "user", user.id)
    db.commit()
    return user, replacement


def revoke_refresh_token(
    db: Session, raw_token: str | None, actor: User | None = None
) -> None:
    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        stored = db.scalar(
            select(RefreshSession)
            .where(RefreshSession.token_hash == token_hash)
            .with_for_update()
        )
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
            record_audit(
                db,
                actor.id if actor else stored.user_id,
                "auth.logout",
                "user",
                stored.user_id,
            )
    db.commit()


def create_user(db: Session, data: UserCreate, actor: User) -> User:
    normalized_email = str(data.email).strip().lower()
    if db.scalar(select(User.id).where(User.normalized_email == normalized_email)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this email already exists"
        )
    user = User(
        full_name=data.full_name.strip(),
        email=normalized_email,
        normalized_email=normalized_email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    try:
        db.flush()
        record_audit(db, actor.id, "user.created", "user", user.id, {"role": user.role})
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this email already exists"
        ) from exc


def update_user(db: Session, target: User, changes: dict, actor: User) -> User:
    if target.id == actor.id and changes.get("is_active") is False:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account"
        )
    demoting_or_deactivating_admin = target.role == Role.ADMINISTRATOR.value and (
        changes.get("role", target.role) != Role.ADMINISTRATOR.value
        or changes.get("is_active", target.is_active) is False
    )
    if demoting_or_deactivating_admin:
        active_admins = db.scalars(
            select(User)
            .where(User.role == Role.ADMINISTRATOR.value, User.is_active.is_(True))
            .with_for_update()
        ).all()
        if len(active_admins) <= 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The last active administrator cannot be removed",
            )
    for key, value in changes.items():
        if value is not None:
            setattr(target, key, value)
    record_audit(db, actor.id, "user.updated", "user", target.id, changes)
    db.commit()
    db.refresh(target)
    return target
