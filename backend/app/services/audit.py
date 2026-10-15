from sqlalchemy.orm import Session

from app.models import AuditAction, AuditLog, ServiceRequest


def record(db: Session, action: AuditAction, request: ServiceRequest, user_id: int) -> None:
    """Stage an audit row in the caller's transaction; the caller commits."""
    db.add(
        AuditLog(
            action=action,
            request_id=request.id,
            request_reference=request.reference,
            user_id=user_id,
        )
    )
