from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import Priority, Role, ServiceType, Status


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    role: Role
    is_active: bool


NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
DescriptionStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)
]


class ServiceRequestCreate(BaseModel):
    client_name: NameStr
    contact_name: NameStr
    service_type: ServiceType
    priority: Priority = Priority.medium
    status: Status = Status.new
    description: DescriptionStr


class ServiceRequestUpdate(BaseModel):
    """Partial update: only fields present in the body are changed."""

    client_name: NameStr | None = None
    contact_name: NameStr | None = None
    service_type: ServiceType | None = None
    priority: Priority | None = None
    status: Status | None = None
    description: DescriptionStr | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "ServiceRequestUpdate":
        nulls = [f for f in self.model_fields_set if getattr(self, f) is None]
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(sorted(nulls))}")
        return self


class ServiceRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    client_name: str
    contact_name: str
    service_type: ServiceType
    priority: Priority
    status: Status
    description: str
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class ServiceRequestPage(BaseModel):
    items: list[ServiceRequestOut]
    total: int
    page: int
    page_size: int


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
