from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaintenancePlanInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    asset_id: UUID
    interval_days: int = Field(gt=0, le=3650)
    next_due_date: date
    description: str | None = Field(default=None, max_length=5000)


class MaintenancePlanOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    asset_id: UUID
    interval_days: int
    next_due_date: date
    description: str | None
    is_active: bool


class WorkOrderInput(BaseModel):
    asset_id: UUID
    plan_id: UUID | None = None
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    due_date: date | None = None


class WorkOrderAssignInput(BaseModel):
    assigned_to_id: UUID
    due_date: date | None = None


class WorkOrderStatusInput(BaseModel):
    status: str = Field(pattern="^(in_progress|completed|cancelled)$")
    resolution: str | None = Field(default=None, max_length=5000)


class WorkOrderOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    asset_id: UUID
    asset_tag: str
    plan_id: UUID | None
    title: str
    description: str | None
    priority: str
    status: str
    requested_by_id: UUID
    assigned_to_id: UUID | None
    due_date: date | None
    completed_at: datetime | None
    resolution: str | None


class NotificationOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    message: str
    read_at: datetime | None
    created_at: datetime
