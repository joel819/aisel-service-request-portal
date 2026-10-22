from typing import Any

from fastapi.testclient import TestClient

Headers = dict[str, str]

VALID_PAYLOAD: dict[str, Any] = {
    "client_name": "Northwind Demo Co",
    "contact_name": "Sam Example",
    "service_type": "business_automation",
    "description": "Automate the monthly invoicing workflow.",
}


def _create(client: TestClient, headers: Headers, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/requests", json={**VALID_PAYLOAD, **overrides}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_read_update_workflow(client: TestClient, auth_headers: Headers) -> None:
    created = _create(client, auth_headers)
    assert created["reference"] == f"SR-{created['id']:05d}"
    assert created["status"] == "new"
    assert created["priority"] == "medium"

    fetched = client.get(f"/api/requests/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json() == created

    updated = client.patch(
        f"/api/requests/{created['id']}",
        json={"status": "in_progress", "priority": "critical"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "critical"
    assert body["client_name"] == created["client_name"]
    assert body["updated_at"] > created["updated_at"]


def test_invalid_priority_returns_422(client: TestClient, auth_headers: Headers) -> None:
    response = client.post(
        "/api/requests", json={**VALID_PAYLOAD, "priority": "urgent"}, headers=auth_headers
    )

    assert response.status_code == 422


def test_missing_required_field_returns_422(client: TestClient, auth_headers: Headers) -> None:
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "client_name"}

    response = client.post("/api/requests", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_patch_invalid_status_returns_422(client: TestClient, auth_headers: Headers) -> None:
    created = _create(client, auth_headers)

    response = client.patch(
        f"/api/requests/{created['id']}", json={"status": "done"}, headers=auth_headers
    )

    assert response.status_code == 422


def test_get_nonexistent_returns_404(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/api/requests/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Service request not found"}


def test_delete_then_get_returns_404(client: TestClient, auth_headers: Headers) -> None:
    created = _create(client, auth_headers)

    deleted = client.delete(f"/api/requests/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    assert client.get(f"/api/requests/{created['id']}", headers=auth_headers).status_code == 404


def test_list_filter_by_status_returns_only_matching(
    client: TestClient, auth_headers: Headers
) -> None:
    _create(client, auth_headers, client_name="Alpha Demo Co")
    _create(client, auth_headers, client_name="Beta Demo Co", status="completed")
    _create(client, auth_headers, client_name="Gamma Demo Co", status="completed")

    response = client.get("/api/requests", params={"status": "completed"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["status"] for item in body["items"]} == {"completed"}


def test_list_search_and_pagination(client: TestClient, auth_headers: Headers) -> None:
    for i in range(3):
        _create(client, auth_headers, client_name=f"Paged Demo Co {i}")
    _create(client, auth_headers, client_name="Other Demo Co")

    response = client.get(
        "/api/requests", params={"q": "paged", "page": 2, "page_size": 2}, headers=auth_headers
    )

    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert len(body["items"]) == 1


def test_list_search_treats_wildcards_literally(client: TestClient, auth_headers: Headers) -> None:
    _create(client, auth_headers)

    response = client.get("/api/requests", params={"q": "%"}, headers=auth_headers)

    assert response.json()["total"] == 0


def test_non_admin_cannot_delete(
    client: TestClient, auth_headers: Headers, member_headers: Headers
) -> None:
    created = _create(client, auth_headers)

    denied = client.delete(f"/api/requests/{created['id']}", headers=member_headers)

    assert denied.status_code == 403
    assert client.get(f"/api/requests/{created['id']}", headers=auth_headers).status_code == 200


def test_non_admin_can_create_and_update(client: TestClient, member_headers: Headers) -> None:
    created = _create(client, member_headers)

    response = client.patch(
        f"/api/requests/{created['id']}", json={"status": "in_review"}, headers=member_headers
    )

    assert response.status_code == 200


def test_member_sees_only_own_requests(
    client: TestClient, auth_headers: Headers, member_headers: Headers
) -> None:
    admin_request = _create(client, auth_headers, client_name="Admin Owned Co")
    own = _create(client, member_headers, client_name="Member Owned Co")

    listing = client.get("/api/requests", headers=member_headers).json()

    assert [item["id"] for item in listing["items"]] == [own["id"]]
    assert listing["total"] == 1
    assert admin_request["id"] not in [item["id"] for item in listing["items"]]


def test_member_cannot_read_update_or_delete_others_request(
    client: TestClient, auth_headers: Headers, member_headers: Headers
) -> None:
    theirs = _create(client, auth_headers)
    url = f"/api/requests/{theirs['id']}"

    assert client.get(url, headers=member_headers).status_code == 404
    assert client.patch(url, json={"status": "completed"}, headers=member_headers).status_code == 404
    assert client.get(url, headers=auth_headers).json()["status"] == "new"


def test_admin_sees_every_request(
    client: TestClient, auth_headers: Headers, member_headers: Headers
) -> None:
    _create(client, auth_headers)
    _create(client, member_headers)

    assert client.get("/api/requests", headers=auth_headers).json()["total"] == 2
