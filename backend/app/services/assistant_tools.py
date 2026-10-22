"""Read-only tools for the AI assistant.

Every tool runs through the same service layer as the normal API and receives the signed-in
user from the server. The model only ever supplies search filters or a request number, so it
cannot see more than that user can already see.
"""
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.models import Priority, ServiceRequest, ServiceType, Status, User
from app.services import requests as request_service
from app.services.requests import RequestFilters

log = logging.getLogger("app.assistant.tools")

DESCRIPTION_LIMIT = 500
MAX_RESULTS = 20


class ToolError(Exception):
    """A problem the model can read and recover from."""


class RequestFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(
        None, max_length=100, description="Text to look for in client, contact, reference or description"
    )
    client_name: str | None = Field(None, max_length=200, description="Part of the client's name")
    statuses: list[Status] | None = Field(None, description="Match any of these statuses")
    priorities: list[Priority] | None = Field(None, description="Match any of these priorities")
    service_type: ServiceType | None = None
    created_after: date | None = Field(None, description="First day to include, YYYY-MM-DD (UTC)")
    created_before: date | None = Field(None, description="First day to exclude, YYYY-MM-DD (UTC)")


class SearchArgs(RequestFilter):
    limit: int = Field(10, ge=1, le=MAX_RESULTS, description="Maximum number of requests to return")


class CountArgs(RequestFilter):
    pass


class GetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: int = Field(ge=1, description="Numeric id of the request; SR-00042 has id 42")


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _filters(args: RequestFilter) -> RequestFilters:
    return RequestFilters(
        q=args.q,
        client_name=args.client_name,
        statuses=tuple(args.statuses) if args.statuses else None,
        priorities=tuple(args.priorities) if args.priorities else None,
        service_type=args.service_type,
        created_from=_start_of_day(args.created_after) if args.created_after else None,
        created_before=_start_of_day(args.created_before) if args.created_before else None,
    )


def _serialize(request: ServiceRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "reference": request.reference,
        "client_name": request.client_name,
        "contact_name": request.contact_name,
        "service_type": request.service_type.value,
        "priority": request.priority.value,
        "status": request.status.value,
        "description": request.description[:DESCRIPTION_LIMIT],
        "created_at": request.created_at.isoformat(),
        "updated_at": request.updated_at.isoformat(),
    }


def _search(db: Session, viewer: User, args: SearchArgs) -> dict[str, Any]:
    filters = _filters(args)
    items, total = request_service.list_requests(db, viewer, filters, page=1, page_size=args.limit)
    return {"total": total, "returned": len(items), "requests": [_serialize(i) for i in items]}


def _count(db: Session, viewer: User, args: CountArgs) -> dict[str, Any]:
    return {"count": request_service.count_requests(db, viewer, _filters(args))}


def _get(db: Session, viewer: User, args: GetArgs) -> dict[str, Any]:
    request = request_service.get_request(db, viewer, args.request_id)
    if request is None:
        raise ToolError("Request not found")
    return _serialize(request)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[Session, User, Any], dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        parameters = self.args.model_json_schema()
        parameters.pop("title", None)
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": parameters},
        }


SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "search_requests",
        "List service requests the user can see, newest first, optionally filtered. Use it to find or "
        "list requests (for example urgent ones this week). Do not use it to count; use count_requests. "
        "Returns the total number of matches and up to `limit` requests.",
        SearchArgs,
        _search,
    ),
    ToolSpec(
        "get_request",
        "Get ONE service request by its numeric id. Use it to summarise or look up a specific request "
        "such as #42. Returns the full request, or an error if it does not exist or is not visible.",
        GetArgs,
        _get,
    ),
    ToolSpec(
        "count_requests",
        "Count the service requests the user can see that match the filters, without listing them. Use it "
        "for 'how many' questions. Returns {\"count\": n}.",
        CountArgs,
        _count,
    ),
)
TOOL_SCHEMAS: list[dict[str, Any]] = [spec.schema() for spec in SPECS]
TOOL_NAMES: frozenset[str] = frozenset(spec.name for spec in SPECS)
_BY_NAME = {spec.name: spec for spec in SPECS}


def run_tool(db: Session, viewer: User, name: str, raw_arguments: str) -> str:
    """Run one tool call. Never raises: every failure becomes a JSON error the model can read."""
    spec = _BY_NAME.get(name)
    if spec is None:
        return json.dumps({"error": f"unknown tool '{name}'", "available": sorted(_BY_NAME)})
    try:
        args = spec.args.model_validate_json(raw_arguments or "{}")
        return json.dumps(spec.run(db, viewer, args))
    except ValidationError as exc:
        details = [f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors()]
        return json.dumps({"error": "invalid arguments", "details": details})
    except ToolError as exc:
        return json.dumps({"error": str(exc)})
    except Exception:
        log.exception("tool failed name=%s", name)
        return json.dumps({"error": "the tool failed"})
