import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ServiceType(str, enum.Enum):
    website_digital_presence = "website_digital_presence"
    business_automation = "business_automation"
    cloud_infrastructure = "cloud_infrastructure"
    devops_observability = "devops_observability"
    ai_automation = "ai_automation"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Role(str, enum.Enum):
    admin = "admin"
    user = "user"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"


class Status(str, enum.Enum):
    new = "new"
    in_review = "in_review"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


def _pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(
        _pg_enum(Role, "user_role"), default=Role.user, server_default=Role.user.value
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ServiceRequest(Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint("char_length(client_name) BETWEEN 2 AND 200", name="ck_client_name_len"),
        CheckConstraint("char_length(contact_name) BETWEEN 2 AND 200", name="ck_contact_name_len"),
        CheckConstraint("char_length(description) BETWEEN 10 AND 5000", name="ck_description_len"),
        Index("ix_service_requests_status", "status"),
        Index("ix_service_requests_priority", "priority"),
        Index("ix_service_requests_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(
        String(20),
        Computed("'SR-' || lpad(id::text, 5, '0')", persisted=True),
        unique=True,
    )
    client_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(200))
    service_type: Mapped[ServiceType] = mapped_column(_pg_enum(ServiceType, "service_type"))
    priority: Mapped[Priority] = mapped_column(
        _pg_enum(Priority, "request_priority"),
        default=Priority.medium,
        server_default=Priority.medium.value,
    )
    status: Mapped[Status] = mapped_column(
        _pg_enum(Status, "request_status"),
        default=Status.new,
        server_default=Status.new.value,
    )
    description: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Append-only record of changes. request_id has no FK because requests are hard-deleted."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[AuditAction] = mapped_column(_pg_enum(AuditAction, "audit_action"))
    request_id: Mapped[int]
    request_reference: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
