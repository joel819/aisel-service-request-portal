import json
from collections.abc import Iterator
from itertools import chain
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_current_user
from app.llm import LLM, get_llm
from app.models import User
from app.schemas import AskRequest
from app.services import assistant as assistant_service
from app.services.rate_limit import assistant_limiter

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


@router.post(
    "/ask",
    summary="Ask the assistant about your service requests (streams Server-Sent Events)",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Events: tool, token, error, done"},
        401: {"description": "Missing or invalid token"},
        429: {"description": "Too many questions"},
        502: {"description": "The language model is unreachable"},
        503: {"description": "The assistant is not configured"},
        504: {"description": "The assistant timed out"},
    },
)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    llm: LLM = Depends(get_llm),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    if not assistant_limiter.allow(str(current_user.id)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many assistant questions. Try again in a minute.",
            headers={"Retry-After": str(assistant_limiter.window_seconds)},
        )
    events = assistant_service.ask(llm, db, current_user, payload.question, settings)
    first = next(events)
    if first["type"] == "error":
        raise HTTPException(first["status_code"], first["message"])
    body: Iterator[str] = (_sse(event) for event in chain([first], events))
    return StreamingResponse(
        body, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
