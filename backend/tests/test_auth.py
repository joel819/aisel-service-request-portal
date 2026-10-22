from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models import User
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def test_login_success_returns_token(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "nope"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_unknown_email_returns_same_401(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": "who@example.com", "password": "x"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_requests_without_token_returns_401(client: TestClient) -> None:
    assert client.get("/api/requests").status_code == 401


def test_requests_with_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/requests", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_requests_with_expired_token_returns_401(client: TestClient, user: User) -> None:
    expired = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        get_settings().jwt_secret,
        "HS256",
    )

    response = client.get("/api/requests", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == TEST_EMAIL
    assert "hashed_password" not in response.json()


def test_login_is_rate_limited(client: TestClient) -> None:
    for _ in range(10):
        client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "wrong"})

    response = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_placeholder_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://x", jwt_secret="change-me-to-a-long-random-string")
