from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class VendorInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    contact_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=2000)


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    contact_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_null_name(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Name cannot be null")
        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("Active state cannot be null")
        return self


class VendorOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    address: str | None
    is_active: bool
