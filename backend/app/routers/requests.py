from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Priority, ServiceRequest, ServiceType, Status, User
from app.schemas import (
    ServiceRequestCreate,
    ServiceRequestOut,
    ServiceRequestPage,
    ServiceRequestUpdate,
)
from app.services import requests as request_service
from app.services.requests import RequestFilters

router = APIRouter(
    prefix="/api/requests",
    tags=["requests"],
    dependencies=[Depends(get_current_user)],
)


def _get_or_404(db: Session, request_id: int) -> ServiceRequest:
    request = request_service.get_request(db, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service request not found")
    return request


@router.get("", response_model=ServiceRequestPage)
def list_requests(
    q: str | None = Query(None, max_length=200),
    status_: Status | None = Query(None, alias="status"),
    priority: Priority | None = None,
    service_type: ServiceType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ServiceRequestPage:
    filters = RequestFilters(q=q, status=status_, priority=priority, service_type=service_type)
    items, total = request_service.list_requests(db, filters, page, page_size)
    return ServiceRequestPage(
        items=[ServiceRequestOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ServiceRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: ServiceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServiceRequest:
    return request_service.create_request(db, payload, current_user.id)


@router.get("/{request_id}", response_model=ServiceRequestOut)
def read_request(request_id: int, db: Session = Depends(get_db)) -> ServiceRequest:
    return _get_or_404(db, request_id)


@router.patch("/{request_id}", response_model=ServiceRequestOut)
def update_request(
    request_id: int,
    payload: ServiceRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServiceRequest:
    request = _get_or_404(db, request_id)
    return request_service.update_request(db, request, payload, current_user.id)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Response:
    request_service.delete_request(db, _get_or_404(db, request_id), admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
