import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.llm import Completed, LLMError, StreamPiece, TextPiece, Usage
from app.models import Priority, ServiceRequest, ServiceType, Status, User

Headers = dict[str, str]


def make_request(db: Session, owner: User, days_old: int = 0, **overrides: Any) -> ServiceRequest:
    values: dict[str, Any] = {
        "client_name": "Acme Demo Ltd",
        "contact_name": "Jane Sample",
        "service_type": ServiceType.cloud_infrastructure,
        "priority": Priority.medium,
        "status": Status.new,
        "description": "Migrate the staging workloads.",
        "created_by_id": owner.id,
    }
    request = ServiceRequest(**{**values, **overrides})
    db.add(request)
    db.commit()
    if days_old:
        request.created_at = datetime.now(UTC) - timedelta(days=days_old)
        db.commit()
    return request


def ask(client: TestClient, headers: Headers, question: str = "show urgent requests") -> Any:
    return client.post("/api/assistant/ask", json={"question": question}, headers=headers)


def parse_sse(body: str) -> list[dict[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        data = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data:
            events.append(json.loads(data[0]))
    return events


def answer_text(response: Any) -> str:
    return "".join(e["text"] for e in parse_sse(response.text) if e["type"] == "token")


def tool_call(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> dict[str, Any]:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def message(text: str | None, *calls: dict[str, Any]) -> Completed:
    body: dict[str, Any] = {"role": "assistant", "content": text}
    if calls:
        body["tool_calls"] = list(calls)
    return Completed(body, "tool_calls" if calls else "stop", Usage(10, 0, 5))


class ScriptedLLM:
    """Plays back one scripted round per call. A round is a list of text pieces ending in a Completed.

    A callable round receives the messages sent so far, so a test can react to tool results.
    """

    name = "scripted"

    def __init__(self, *rounds: Any, repeat_last: bool = False) -> None:
        self.rounds = list(rounds)
        self.repeat_last = repeat_last
        self.seen: list[list[dict[str, Any]]] = []

    def stream_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], deadline: float
    ) -> Iterator[StreamPiece]:
        self.seen.append(json.loads(json.dumps(messages, default=str)))
        step = self.rounds[0] if self.repeat_last and len(self.rounds) == 1 else self.rounds.pop(0)
        pieces = step(messages) if callable(step) else step
        for piece in pieces:
            if isinstance(piece, Exception):
                raise piece
            yield piece

    def tool_messages(self) -> list[str]:
        return [m["content"] for m in self.seen[-1] if m["role"] == "tool"]


__all__ = ["LLMError", "TextPiece"]
