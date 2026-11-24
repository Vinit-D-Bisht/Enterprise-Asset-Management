from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class DashboardOutput(BaseModel):
    total_assets: int
    available_assets: int
    assigned_assets: int
    assets_in_repair: int
    open_work_orders: int
    overdue_work_orders: int
    maintenance_due: int
    warranties_expiring_30_days: int


class PersonalOverview(BaseModel):
    assigned_assets: int
    requested_work_orders: int
    assigned_work_orders: int
    unread_notifications: int


class DepreciationRow(BaseModel):
    asset_id: UUID
    asset_tag: str
    name: str
    purchase_cost: Decimal
    residual_value: Decimal
    accumulated_depreciation: Decimal
    book_value: Decimal
    as_of_date: date


class DepreciationReport(BaseModel):
    as_of_date: date
    company_currency: str
    items: list[DepreciationRow]
    total: int
    page: int
    page_size: int
    total_cost: Decimal
    total_accumulated_depreciation: Decimal
    total_book_value: Decimal


class AuditOutput(BaseModel):
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: str
    details: dict
    created_at: datetime
