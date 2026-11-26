from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.auth import UserOutput


class InitialSetupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    confirm_password: str = Field(min_length=12, max_length=200)
    sample_data: bool

    @model_validator(mode="after")
    def validate_confirmation(self):
        if self.password != self.confirm_password:
            raise ValueError("Password confirmation does not match")
        normalized_name = self.full_name.strip()
        if len(normalized_name) < 2:
            raise ValueError("Name must contain at least two non-space characters")
        self.full_name = normalized_name
        return self


class SetupStatus(BaseModel):
    setup_required: bool


class InitialSetupResponse(BaseModel):
    setup_complete: bool
    sample_data_created: bool
    administrator: UserOutput
