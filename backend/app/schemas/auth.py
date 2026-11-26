from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.common import ORMModel


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    role: str = Field(pattern="^(administrator|asset_manager|technician|employee)$")
    department_id: UUID | None = None

    @field_validator("full_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least two non-space characters")
        return value


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = Field(
        default=None, pattern="^(administrator|asset_manager|technician|employee)$"
    )
    is_active: bool | None = None
    department_id: UUID | None = None

    @model_validator(mode="after")
    def reject_null_values(self):
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set & {"role", "is_active"}
        ):
            raise ValueError("Role and active state cannot be null")
        return self


class UserOutput(ORMModel):
    id: UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    department_id: UUID | None = None
    department_name: str | None = None


class CurrentUserOutput(UserOutput):
    pass


class UserOptionOutput(BaseModel):
    id: UUID
    full_name: str
    role: str
