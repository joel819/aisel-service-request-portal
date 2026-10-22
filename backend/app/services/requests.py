from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditAction, Priority, Role, ServiceRequest, ServiceType, Status, User
from app.schemas import ServiceRequestCreate, ServiceRequestUpdate
from app.services import audit


@dataclass(frozen=True)
class RequestFilters:
    q: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    service_type: ServiceType | None = None
    statuses: tuple[Status, ...] | None = None
    priorities: tuple[Priority, ...] | None = None
    client_name: str | None = None
    created_from: datetime | None = None
    created_before: datetime | None = None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _visible_to(stmt: Select, viewer: User) -> Select:
    """The one access rule: admins see every request, everyone else only their own."""
    if viewer.role == Role.admin:
        return stmt
    return stmt.where(ServiceRequest.created_by_id == viewer.id)


def _apply_filters(stmt: Select, filters: RequestFilters) -> Select:
    if filters.status is not None:
        stmt = stmt.where(ServiceRequest.status == filters.status)
    if filters.priority is not None:
        stmt = stmt.where(ServiceRequest.priority == filters.priority)
    if filters.service_type is not None:
        stmt = stmt.where(ServiceRequest.service_type == filters.service_type)
    if filters.statuses:
        stmt = stmt.where(ServiceRequest.status.in_(filters.statuses))
    if filters.priorities:
        stmt = stmt.where(ServiceRequest.priority.in_(filters.priorities))
    if filters.client_name:
        pattern = f"%{_escape_like(filters.client_name.strip())}%"
        stmt = stmt.where(ServiceRequest.client_name.ilike(pattern, escape="\\"))
    if filters.created_from is not None:
        stmt = stmt.where(ServiceRequest.created_at >= filters.created_from)
    if filters.created_before is not None:
        stmt = stmt.where(ServiceRequest.created_at < filters.created_before)
    if filters.q:
        pattern = f"%{_escape_like(filters.q.strip())}%"
        columns = (
            ServiceRequest.client_name,
            ServiceRequest.contact_name,
            ServiceRequest.reference,
            ServiceRequest.description,
        )
        stmt = stmt.where(or_(*(c.ilike(pattern, escape="\\") for c in columns)))
    return stmt


def list_requests(
    db: Session, viewer: User, filters: RequestFilters, page: int, page_size: int
) -> tuple[list[ServiceRequest], int]:
    base = _apply_filters(_visible_to(select(ServiceRequest), viewer), filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def count_requests(db: Session, viewer: User, filters: RequestFilters) -> int:
    base = _apply_filters(_visible_to(select(ServiceRequest), viewer), filters)
    return db.scalar(select(func.count()).select_from(base.subquery())) or 0


def get_request(db: Session, viewer: User, request_id: int) -> ServiceRequest | None:
    stmt = _visible_to(select(ServiceRequest).where(ServiceRequest.id == request_id), viewer)
    return db.scalar(stmt)


def create_request(db: Session, data: ServiceRequestCreate, user_id: int) -> ServiceRequest:
    request = ServiceRequest(**data.model_dump(), created_by_id=user_id)
    db.add(request)
    db.flush()
    db.refresh(request)
    audit.record(db, AuditAction.create, request, user_id)
    db.commit()
    return request


def update_request(
    db: Session, request: ServiceRequest, data: ServiceRequestUpdate, user_id: int
) -> ServiceRequest:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(request, field, value)
    audit.record(db, AuditAction.update, request, user_id)
    db.commit()
    db.refresh(request)
    return request


def delete_request(db: Session, request: ServiceRequest, user_id: int) -> None:
    audit.record(db, AuditAction.delete, request, user_id)
    db.delete(request)
    db.commit()
