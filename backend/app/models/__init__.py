from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    ADMINISTRATOR = "administrator"
    ASSET_MANAGER = "asset_manager"
    TECHNICIAN = "technician"
    EMPLOYEE = "employee"


class AssetStatus(StrEnum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    IN_REPAIR = "in_repair"
    RETIRED = "retired"


class WorkOrderStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkOrderPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class EntityMixin(TimestampMixin):
    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )


class Department(EntityMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        Index("uq_departments_name_lower", text("lower(trim(name))"), unique=True),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class User(EntityMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('administrator', 'asset_manager', 'technician', 'employee')",
            name="ck_users_role",
        ),
        Index("ix_users_normalized_email", "normalized_email", unique=True),
    )

    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=Role.EMPLOYEE.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id"), index=True
    )

    department: Mapped[Department | None] = relationship()
    refresh_sessions: Mapped[list["RefreshSession"]] = relationship(
        back_populates="user"
    )

    @property
    def department_name(self) -> str | None:
        return self.department.name if self.department else None


class RefreshSession(EntityMixin, Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (
        Index("ix_refresh_sessions_user_id", "user_id"),
        Index("ix_refresh_sessions_family_id", "family_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_hash: Mapped[str | None] = mapped_column(String(64))
    user: Mapped[User] = relationship(back_populates="refresh_sessions")


class LoginThrottleBucket(Base):
    """Opaque per-email/IP login failure counters; never stores raw identifiers."""

    __tablename__ = "login_throttle_buckets"
    __table_args__ = (
        CheckConstraint(
            "failure_count >= 0", name="ck_login_throttle_failures_nonnegative"
        ),
        Index("ix_login_throttle_window_started", "window_started_at"),
    )

    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssetCategory(EntityMixin, Base):
    __tablename__ = "asset_categories"
    __table_args__ = (Index("ix_asset_categories_name", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Location(EntityMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (Index("ix_locations_name", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str | None] = mapped_column(String(40), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Vendor(EntityMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (Index("ix_vendors_name", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(180), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Asset(EntityMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "purchase_cost >= 0", name="ck_assets_purchase_cost_nonnegative"
        ),
        CheckConstraint("residual_value >= 0", name="ck_assets_residual_nonnegative"),
        CheckConstraint(
            "residual_value <= purchase_cost", name="ck_assets_residual_lte_cost"
        ),
        CheckConstraint(
            "useful_life_months > 0", name="ck_assets_useful_life_positive"
        ),
        CheckConstraint(
            "status IN ('available', 'assigned', 'in_repair', 'retired')",
            name="ck_assets_status",
        ),
        Index("ix_assets_asset_tag", "asset_tag", unique=True),
        Index("ix_assets_serial_number", "serial_number", unique=True),
        Index("ix_assets_category_id", "category_id"),
        Index("ix_assets_location_id", "location_id"),
        Index("ix_assets_status", "status"),
    )

    asset_tag: Mapped[str] = mapped_column(String(80), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_categories.id"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    residual_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AssetStatus.AVAILABLE.value
    )

    category: Mapped[AssetCategory] = relationship()
    location: Mapped[Location] = relationship()
    vendor: Mapped[Vendor | None] = relationship()
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="asset")
    warranties: Mapped[list["Warranty"]] = relationship(back_populates="asset")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="asset")


class Assignment(EntityMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index(
            "uq_assignments_active_asset",
            "asset_id",
            unique=True,
            postgresql_where=text("returned_at IS NULL"),
            sqlite_where=text("returned_at IS NULL"),
        ),
        Index("ix_assignments_user_id", "user_id"),
    )

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="assignments")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    assigned_by: Mapped[User] = relationship(foreign_keys=[assigned_by_id])


class Transfer(EntityMixin, Base):
    __tablename__ = "transfers"
    __table_args__ = (Index("ix_transfers_asset_created", "asset_id", "created_at"),)

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), nullable=False)
    from_location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    to_location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    transferred_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Warranty(EntityMixin, Base):
    __tablename__ = "warranties"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_warranties_dates"),
        Index("ix_warranties_asset_id", "asset_id"),
    )

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), nullable=False)
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    terms: Mapped[str | None] = mapped_column(Text)
    asset: Mapped[Asset] = relationship(back_populates="warranties")


class MaintenancePlan(EntityMixin, Base):
    __tablename__ = "maintenance_plans"
    __table_args__ = (
        CheckConstraint(
            "interval_days > 0", name="ck_maintenance_plans_interval_positive"
        ),
        Index("ix_maintenance_plans_next_due", "next_due_date"),
    )

    name: Mapped[str] = mapped_column(String(180), nullable=False)
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorkOrder(EntityMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'cancelled')",
            name="ck_work_orders_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_work_orders_priority",
        ),
        Index("ix_work_orders_status_due", "status", "due_date"),
        Index("ix_work_orders_assignee", "assigned_to_id", "status"),
    )

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), nullable=False)
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("maintenance_plans.id"))
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WorkOrderPriority.MEDIUM.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WorkOrderStatus.OPEN.value
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="work_orders")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id])


class Notification(EntityMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("uq_notifications_dedupe_key", "dedupe_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(240))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
