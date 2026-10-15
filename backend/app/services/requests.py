from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Priority, ServiceRequest, ServiceType, Status
from app.schemas import ServiceRequestCreate, ServiceRequestUpdate


@dataclass(frozen=True)
class RequestFilters:
    q: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    service_type: ServiceType | None = None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(stmt, filters: RequestFilters):
    if filters.status is not None:
        stmt = stmt.where(ServiceRequest.status == filters.status)
    if filters.priority is not None:
        stmt = stmt.where(ServiceRequest.priority == filters.priority)
    if filters.service_type is not None:
        stmt = stmt.where(ServiceRequest.service_type == filters.service_type)
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
    db: Session, filters: RequestFilters, page: int, page_size: int
) -> tuple[list[ServiceRequest], int]:
    base = _apply_filters(select(ServiceRequest), filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def get_request(db: Session, request_id: int) -> ServiceRequest | None:
    return db.get(ServiceRequest, request_id)


def create_request(db: Session, data: ServiceRequestCreate, user_id: int) -> ServiceRequest:
    request = ServiceRequest(**data.model_dump(), created_by_id=user_id)
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def update_request(
    db: Session, request: ServiceRequest, data: ServiceRequestUpdate
) -> ServiceRequest:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(request, field, value)
    db.commit()
    db.refresh(request)
    return request


def delete_request(db: Session, request: ServiceRequest) -> None:
    db.delete(request)
    db.commit()
