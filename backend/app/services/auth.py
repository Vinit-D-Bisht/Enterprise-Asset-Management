import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import Department, LoginThrottleBucket, RefreshSession, Role, User
from app.schemas.auth import LoginInput, UserCreate
from app.services.audit import record_audit

DUMMY_LOGIN_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_PAIR_FAILURE_LIMIT = 5
LOGIN_IP_FAILURE_LIMIT = 30


def _login_bucket_keys(email: str, source_ip: str) -> tuple[str, str]:
    secret = settings.JWT_SECRET_KEY.encode("utf-8")
    pair = hmac.new(
        secret, f"pair\0{source_ip}\0{email}".encode(), hashlib.sha256
    ).hexdigest()
    ip_only = hmac.new(secret, f"ip\0{source_ip}".encode(), hashlib.sha256).hexdigest()
    return pair, ip_only


def _ensure_login_buckets(db: Session, keys: tuple[str, str], now: datetime) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        for key in keys:
            if db.get(LoginThrottleBucket, key) is None:
                db.add(
                    LoginThrottleBucket(
                        bucket_key=key, failure_count=0, window_started_at=now
                    )
                )
        db.flush()
        return
    for key in keys:
        statement = (
            insert(LoginThrottleBucket)
            .values(bucket_key=key, failure_count=0, window_started_at=now)
            .on_conflict_do_nothing(index_elements=["bucket_key"])
        )
        db.execute(statement)


def _locked_login_buckets(db: Session, keys: tuple[str, str], now: datetime):
    _ensure_login_buckets(db, keys, now)
    rows = db.scalars(
        select(LoginThrottleBucket)
        .where(LoginThrottleBucket.bucket_key.in_(keys))
        .with_for_update()
    ).all()
    for row in rows:
        started = row.window_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started + LOGIN_FAILURE_WINDOW <= now:
            row.failure_count = 0
            row.window_started_at = now
            row.blocked_until = None
    return {row.bucket_key: row for row in rows}


def authenticate(
    db: Session, credentials: LoginInput, source_ip: str = "unknown"
) -> tuple[User, str]:
    normalized_email = str(credentials.email).strip().lower()
    now = datetime.now(timezone.utc)
    keys = _login_bucket_keys(normalized_email, source_ip)
    buckets = _locked_login_buckets(db, keys, now)
    retry_seconds = 0
    for row in buckets.values():
        if row.blocked_until is not None:
            blocked_until = row.blocked_until
            if blocked_until.tzinfo is None:
                blocked_until = blocked_until.replace(tzinfo=timezone.utc)
            retry_seconds = max(
                retry_seconds, int((blocked_until - now).total_seconds() + 0.999)
            )
    if retry_seconds > 0:
        db.rollback()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_seconds)},
        )

    user = db.scalar(select(User).where(User.normalized_email == normalized_email))
    valid_password = verify_password(
        credentials.password,
        user.password_hash if user is not None else DUMMY_LOGIN_PASSWORD_HASH,
    )
    if user is None or not valid_password:
        db.execute(
            delete(LoginThrottleBucket)
            .where(LoginThrottleBucket.window_started_at < now - timedelta(days=1))
            .execution_options(synchronize_session=False)
        )
        pair_bucket = buckets[keys[0]]
        ip_bucket = buckets[keys[1]]
        pair_bucket.failure_count += 1
        ip_bucket.failure_count += 1
        if pair_bucket.failure_count >= LOGIN_PAIR_FAILURE_LIMIT:
            pair_bucket.blocked_until = now + LOGIN_FAILURE_WINDOW
        if ip_bucket.failure_count >= LOGIN_IP_FAILURE_LIMIT:
            ip_bucket.blocked_until = now + LOGIN_FAILURE_WINDOW
        newly_blocked = (
            pair_bucket.blocked_until is not None or ip_bucket.blocked_until is not None
        )
        db.commit()
        if newly_blocked:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many login attempts. Try again later.",
                headers={"Retry-After": str(int(LOGIN_FAILURE_WINDOW.total_seconds()))},
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        buckets[keys[0]].failure_count += 1
        buckets[keys[1]].failure_count += 1
        if buckets[keys[0]].failure_count >= LOGIN_PAIR_FAILURE_LIMIT:
            buckets[keys[0]].blocked_until = now + LOGIN_FAILURE_WINDOW
        if buckets[keys[1]].failure_count >= LOGIN_IP_FAILURE_LIMIT:
            buckets[keys[1]].blocked_until = now + LOGIN_FAILURE_WINDOW
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    db.execute(
        delete(LoginThrottleBucket)
        .where(LoginThrottleBucket.bucket_key == keys[0])
        .execution_options(synchronize_session=False)
    )
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
    if data.department_id and db.get(Department, data.department_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown department")
    user = User(
        full_name=data.full_name.strip(),
        email=normalized_email,
        normalized_email=normalized_email,
        password_hash=hash_password(data.password),
        role=data.role,
        department_id=data.department_id,
    )
    db.add(user)
    try:
        db.flush()
        record_audit(
            db,
            actor.id,
            "user.created",
            "user",
            user.id,
            {
                "role": user.role,
                "department_id": str(user.department_id)
                if user.department_id
                else None,
            },
        )
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this email already exists"
        ) from exc


def update_user(db: Session, target: User, changes: dict, actor: User) -> User:
    department_id = changes.get("department_id")
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown department")
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
        if value is not None or key == "department_id":
            setattr(target, key, value)
    audit_changes = {
        key: str(value) if isinstance(value, UUID) else value
        for key, value in changes.items()
    }
    record_audit(db, actor.id, "user.updated", "user", target.id, audit_changes)
    db.commit()
    db.refresh(target)
    return target
