"""LLM providers behind one streaming interface (adapted from agent-kit ai-llm-integration).

    MockLLM               offline and deterministic: used by tests, evals and the local demo
    OpenAICompatibleLLM   any /chat/completions API (OpenAI, DeepSeek, Groq, Ollama, vLLM...)

Both implement stream_chat(): they yield TextPiece items while the model writes, then one
Completed item with the full assistant message, the finish reason and the token usage.
"""
import json
import logging
import random
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings

log = logging.getLogger("app.llm")

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
MAX_OUTPUT_TOKENS = 1000


class LLMError(Exception):
    """The provider failed for good (after retries)."""


class LLMTimeout(LLMError):
    """The overall time budget for one question ran out."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.cached_tokens += other.cached_tokens
        self.completion_tokens += other.completion_tokens


@dataclass(frozen=True)
class TextPiece:
    text: str


@dataclass(frozen=True)
class Completed:
    message: dict[str, Any]
    finish_reason: str
    usage: Usage


StreamPiece = TextPiece | Completed


class LLM(Protocol):
    name: str

    def stream_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], deadline: float
    ) -> Iterator[StreamPiece]: ...


def _usage_from(raw: dict[str, Any]) -> Usage:
    cached = raw.get("prompt_cache_hit_tokens")
    if cached is None:
        cached = (raw.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return Usage(raw.get("prompt_tokens") or 0, cached or 0, raw.get("completion_tokens") or 0)


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: str | None = None) -> None:
        super().__init__(reason)
        self.retry_after = retry_after


class OpenAICompatibleLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_retries: int = 2,
        base_delay_s: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not (base_url and api_key and model):
            raise ValueError("LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must all be set")
        self.model = model
        self.name = f"openai-compatible:{model}"
        self.max_retries, self.base_delay_s = max_retries, base_delay_s
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def stream_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], deadline: float
    ) -> Iterator[StreamPiece]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": 0,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        for attempt in range(self.max_retries + 1):
            started = False
            try:
                for piece in self._stream_once(body, deadline):
                    started = True
                    yield piece
                return
            except (_Retryable, httpx.TimeoutException, httpx.TransportError) as exc:
                if started:
                    raise LLMError("the provider connection broke mid-answer") from exc
                if attempt == self.max_retries:
                    raise LLMError(f"gave up after {attempt + 1} attempts: {exc}") from exc
                delay = self.base_delay_s * 2**attempt * (0.5 + random.random())
                retry_after = getattr(exc, "retry_after", None)
                if retry_after and retry_after.isdigit():
                    delay = max(delay, float(retry_after))
                if time.monotonic() + delay >= deadline:
                    raise LLMTimeout("no time left to retry") from exc
                log.info("llm retry attempt=%d in %.2fs (%s)", attempt + 1, delay, exc)
                time.sleep(delay)

    def _stream_once(self, body: dict[str, Any], deadline: float) -> Iterator[StreamPiece]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LLMTimeout("time budget used up")
        timeout = httpx.Timeout(remaining, connect=min(5.0, remaining))
        with self.client.stream("POST", "/chat/completions", json=body, timeout=timeout) as response:
            if response.status_code != 200:
                response.read()
                if response.status_code not in RETRYABLE_STATUS:
                    raise LLMError(f"HTTP {response.status_code} from provider (not retryable)")
                raise _Retryable(f"HTTP {response.status_code}", response.headers.get("retry-after"))
            yield from _read_stream(response.iter_lines(), deadline)


def _read_stream(lines: Iterator[str], deadline: float) -> Iterator[StreamPiece]:
    content, reasoning, finish, usage = "", "", "stop", Usage()
    calls: dict[int, dict[str, Any]] = {}
    for line in lines:
        if time.monotonic() > deadline:
            raise LLMTimeout("time budget used up")
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError as exc:
            raise LLMError("the provider sent invalid JSON") from exc
        if chunk.get("usage"):
            usage = _usage_from(chunk["usage"])
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content += delta["content"]
                yield TextPiece(delta["content"])
            reasoning += delta.get("reasoning_content") or ""
            for part in delta.get("tool_calls") or []:
                slot = calls.setdefault(
                    part.get("index", 0),
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                slot["id"] = part.get("id") or slot["id"]
                function = part.get("function") or {}
                slot["function"]["name"] += function.get("name") or ""
                slot["function"]["arguments"] += function.get("arguments") or ""
            finish = choice.get("finish_reason") or finish
    message: dict[str, Any] = {"role": "assistant", "content": content or None}
    if calls:
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
    if reasoning:
        message["reasoning_content"] = reasoning
    yield Completed(message, finish, usage)


TOOL_RESULT = re.compile(r"<tool_result[^>]*>\n(.*)\n</tool_result>", re.S)
REQUEST_ID = re.compile(r"(?:request\s*#?|#|SR-0*)(\d+)", re.I)
TODAY = re.compile(r"Today \(UTC\): (\d{4}-\d{2}-\d{2})")
CLIENT = re.compile(r"for (?:client )?(.+?)[?.!]*$", re.I)


class MockLLM:
    """A rule-based stand-in that reads the conversation, so the real tool loop runs end to end.

    It picks a tool from the question, then writes the answer from the tool result. It does not
    obey instructions found inside tool results, which is exactly what the evals rely on.
    """

    name = "mock"

    def stream_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], deadline: float
    ) -> Iterator[StreamPiece]:
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        turn = messages[last_user:]
        results = [m["content"] for m in turn if m["role"] == "tool"]
        question = turn[0]["content"]
        if results:
            message: dict[str, Any] = {"role": "assistant", "content": _compose(results)}
        else:
            call = _choose_tool(question)
            if call:
                message = {"role": "assistant", "content": None, "tool_calls": [call]}
            else:
                message = {
                    "role": "assistant",
                    "content": "I can search requests, show one by its number, or count them.",
                }
        text = message["content"] or ""
        for word in re.findall(r"\S+\s*", text):
            yield TextPiece(word)
        size = sum(len(str(m.get("content") or "")) for m in messages) // 4
        yield Completed(message, "tool_calls" if message.get("tool_calls") else "stop", Usage(size, 0, len(text) // 4))


def _choose_tool(question: str) -> dict[str, Any] | None:
    lowered = question.lower()
    today_match = TODAY.search(question)
    today = date.fromisoformat(today_match.group(1)) if today_match else date.today()
    name, args = "", {}
    if match := REQUEST_ID.search(question.split("Question:")[-1]):
        name, args = "get_request", {"request_id": int(match.group(1))}
    elif "how many" in lowered or "count" in lowered:
        name, args = "count_requests", {}
    elif any(word in lowered for word in ("urgent", "critical", "high priority")):
        name, args = "search_requests", {"priorities": ["high", "critical"]}
    elif any(word in lowered for word in ("show", "list", "find", "search")):
        name, args = "search_requests", {}
    if not name:
        return None
    if name != "get_request":
        if "open" in lowered:
            args["statuses"] = ["new", "in_review", "in_progress"]
        if "this week" in lowered:
            args["created_after"] = (today - timedelta(days=today.weekday())).isoformat()
        if client := CLIENT.search(question.split("Question:")[-1]):
            if "client" in lowered:
                args["client_name"] = client.group(1)
    return {"id": "call_1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _compose(results: list[str]) -> str:
    match = TOOL_RESULT.search(results[-1])
    try:
        data = json.loads(match.group(1)) if match else json.loads(results[-1])
    except json.JSONDecodeError:
        return "I could not read the tool result."
    if "error" in data:
        return f"I could not complete that: {data['error']}."
    if "count" in data:
        return f"There are {data['count']} matching requests."
    if "requests" in data:
        if not data["requests"]:
            return "I found no matching requests."
        lines = [f"I found {data['total']} matching requests:"]
        lines += [
            f"- {r['reference']}: {r['client_name']} ({r['priority']}, {r['status']})"
            for r in data["requests"]
        ]
        return "\n".join(lines)
    return (
        f"{data['reference']} is a {data['priority']}-priority request from {data['client_name']}, "
        f"status {data['status']}. {data['description']}"
    )


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "mock":
        return MockLLM()
    if settings.llm_provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleLLM(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            max_retries=settings.llm_max_retries,
        )
    raise ValueError(f"unknown LLM_PROVIDER {settings.llm_provider!r} (use mock or openai)")


@lru_cache
def _cached_llm() -> LLM:
    return build_llm(get_settings())


def get_llm() -> LLM:
    try:
        return _cached_llm()
    except ValueError as exc:
        log.error("assistant not configured: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The AI assistant is not configured") from exc
