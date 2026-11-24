from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class LocationInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)


class DirectoryOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None = None
    code: str | None = None


class AssetInput(BaseModel):
    asset_tag: str = Field(min_length=1, max_length=80)
    serial_number: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    category_id: UUID
    location_id: UUID
    vendor_id: UUID | None = None
    purchase_date: date
    purchase_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    residual_value: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    useful_life_months: int = Field(gt=0, le=1200)

    @model_validator(mode="after")
    def residual_cannot_exceed_cost(self):
        if self.residual_value > self.purchase_cost:
            raise ValueError("Residual value cannot exceed purchase cost")
        return self


class AssetUpdate(BaseModel):
    serial_number: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    category_id: UUID | None = None
    location_id: UUID | None = None
    vendor_id: UUID | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    residual_value: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    useful_life_months: int | None = Field(default=None, gt=0, le=1200)

    @model_validator(mode="after")
    def reject_null_for_required_asset_fields(self):
        required = {
            "name",
            "category_id",
            "location_id",
            "purchase_date",
            "purchase_cost",
            "residual_value",
            "useful_life_months",
        }
        invalid = required.intersection(self.model_fields_set)
        nulls = [field for field in invalid if getattr(self, field) is None]
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(sorted(nulls))}")
        return self


class AssetOutput(BaseModel):
    id: UUID
    asset_tag: str
    serial_number: str | None
    name: str
    description: str | None
    category_id: UUID
    category_name: str
    location_id: UUID
    location_name: str
    vendor_id: UUID | None
    purchase_date: date
    purchase_cost: Decimal
    company_currency: str
    residual_value: Decimal
    useful_life_months: int
    status: str
    current_assignee_id: UUID | None = None
    current_assignee_name: str | None = None


class AssetSummaryOutput(BaseModel):
    id: UUID
    asset_tag: str
    serial_number: str | None
    name: str
    description: str | None
    category_id: UUID
    category_name: str
    location_id: UUID
    location_name: str
    status: str
    current_assignee_id: UUID | None = None
    current_assignee_name: str | None = None


class AssignmentOutput(BaseModel):
    id: UUID
    asset_id: UUID
    asset_tag: str
    user_id: UUID
    user_name: str
    assigned_by_id: UUID
    assigned_at: datetime
    returned_at: datetime | None
    notes: str | None


class AssignmentInput(BaseModel):
    user_id: UUID
    notes: str | None = Field(default=None, max_length=2000)


class ReturnInput(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class TransferInput(BaseModel):
    to_location_id: UUID
    reason: str | None = Field(default=None, max_length=2000)


class TransferOutput(BaseModel):
    id: UUID
    asset_id: UUID
    from_location_id: UUID
    to_location_id: UUID
    transferred_at: datetime


class WarrantyInput(BaseModel):
    vendor_id: UUID | None = None
    start_date: date
    end_date: date
    terms: str | None = Field(default=None, max_length=5000)


class WarrantyOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    asset_id: UUID
    vendor_id: UUID | None
    start_date: date
    end_date: date
    terms: str | None
