import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import Priority, Status, User
from app.services import assistant_tools
from app.services.assistant_tools import TOOL_SCHEMAS, run_tool
from tests.assistant_helpers import make_request


def call(db: Session, viewer: User, name: str, args: dict) -> dict:
    return json.loads(run_tool(db, viewer, name, json.dumps(args)))


def test_tool_schemas_are_stable_and_read_only() -> None:
    names = [schema["function"]["name"] for schema in TOOL_SCHEMAS]

    assert names == ["search_requests", "get_request", "count_requests"]


def test_search_filters_and_limit(user: User, db: Session) -> None:
    make_request(db, user, client_name="Old Demo Co", days_old=30)
    for i in range(3):
        make_request(db, user, client_name=f"Recent {i}", status=Status.in_progress)
    cutoff = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()

    recent = call(db, user, "search_requests", {"created_after": cutoff})
    limited = call(db, user, "search_requests", {"statuses": ["in_progress"], "limit": 2})

    assert recent["total"] == 3 and "Old Demo Co" not in json.dumps(recent)
    assert limited["total"] == 3 and limited["returned"] == 2


def test_count_matches_search_total(user: User, db: Session) -> None:
    make_request(db, user, priority=Priority.high)
    make_request(db, user, priority=Priority.low)

    assert call(db, user, "count_requests", {"priorities": ["high", "critical"]}) == {"count": 1}


def test_results_never_include_the_owner_or_audit_fields(user: User, db: Session) -> None:
    request = make_request(db, user)

    data = call(db, user, "get_request", {"request_id": request.id})

    assert data["reference"] == request.reference
    assert "created_by_id" not in data


def test_invalid_input_comes_back_as_json_errors(user: User, db: Session) -> None:
    assert "invalid arguments" in call(db, user, "search_requests", {"limit": 500})["error"]
    assert "invalid arguments" in call(db, user, "search_requests", {"user_id": 1})["error"]
    assert "invalid arguments" in call(db, user, "get_request", {"request_id": "abc"})["error"]
    assert "unknown tool" in call(db, user, "delete_request", {})["error"]
    assert "invalid arguments" in json.loads(run_tool(db, user, "get_request", "{not json"))["error"]


def test_long_descriptions_are_trimmed(user: User, db: Session) -> None:
    request = make_request(db, user, description="x" * 4000)

    data = call(db, user, "get_request", {"request_id": request.id})

    assert len(data["description"]) == 500


def test_a_crashing_tool_returns_a_generic_error_and_hides_details(
    user: User, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_: object) -> dict:
        raise RuntimeError("database password is hunter2")

    monkeypatch.setitem(
        assistant_tools._BY_NAME, "count_requests", replace(assistant_tools._BY_NAME["count_requests"], run=explode)
    )

    result = run_tool(db, user, "count_requests", "{}")

    assert json.loads(result) == {"error": "the tool failed"}
    assert "hunter2" not in result
