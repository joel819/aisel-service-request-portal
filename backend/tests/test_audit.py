from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditAction, AuditLog, User

PAYLOAD = {
    "client_name": "Initech Demo Ltd",
    "contact_name": "Robin Sample",
    "service_type": "ai_automation",
    "description": "Prototype an assistant for the support team.",
}


def test_create_update_delete_are_audited(
    client: TestClient, auth_headers: dict[str, str], db: Session, user: User
) -> None:
    created = client.post("/api/requests", json=PAYLOAD, headers=auth_headers).json()
    client.patch(f"/api/requests/{created['id']}", json={"priority": "high"}, headers=auth_headers)
    client.delete(f"/api/requests/{created['id']}", headers=auth_headers)

    rows = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()

    assert [r.action for r in rows] == [AuditAction.create, AuditAction.update, AuditAction.delete]
    assert {r.request_id for r in rows} == {created["id"]}
    assert {r.request_reference for r in rows} == {created["reference"]}
    assert {r.user_id for r in rows} == {user.id}
    assert all(r.created_at is not None for r in rows)
