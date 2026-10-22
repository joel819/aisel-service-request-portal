import json
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from app.llm import Completed, LLMError, LLMTimeout, OpenAICompatibleLLM, TextPiece

TOOLS = [{"type": "function", "function": {"name": "get_request", "parameters": {"type": "object"}}}]
MESSAGES = [{"role": "user", "content": "hi"}]


def sse(*chunks: dict[str, Any] | str) -> bytes:
    lines = [c if isinstance(c, str) else json.dumps(c) for c in chunks]
    return "".join(f"data: {line}\n\n" for line in lines).encode()


def delta(**fields: Any) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": fields, "finish_reason": None}]}


def build(handler: Callable[[httpx.Request], httpx.Response], retries: int = 2) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        "http://llm.test/v1", "sk-secret-key", "some-model",
        max_retries=retries, base_delay_s=0, transport=httpx.MockTransport(handler),
    )


def run(llm: OpenAICompatibleLLM, seconds: float = 5) -> list[Any]:
    return list(llm.stream_chat(MESSAGES, TOOLS, time.monotonic() + seconds))


def test_streams_text_and_reads_usage() -> None:
    body = sse(
        delta(content="Hel"), delta(content="lo"),
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 20, "completion_tokens": 3,
                                  "prompt_tokens_details": {"cached_tokens": 8}}},
        "[DONE]",
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body)

    pieces = run(build(handler))

    assert [p.text for p in pieces if isinstance(p, TextPiece)] == ["Hel", "lo"]
    done = pieces[-1]
    assert isinstance(done, Completed)
    assert done.message == {"role": "assistant", "content": "Hello"}
    assert done.finish_reason == "stop"
    assert (done.usage.prompt_tokens, done.usage.cached_tokens, done.usage.completion_tokens) == (20, 8, 3)
    request = json.loads(seen[0].content)
    assert request["stream"] is True and request["tools"] == TOOLS and request["model"] == "some-model"
    assert seen[0].headers["authorization"] == "Bearer sk-secret-key"
    assert str(seen[0].url) == "http://llm.test/v1/chat/completions"


def test_assembles_tool_calls_split_across_chunks() -> None:
    body = sse(
        delta(tool_calls=[{"index": 0, "id": "call_a", "type": "function",
                           "function": {"name": "get_request", "arguments": ""}}]),
        delta(tool_calls=[{"index": 0, "function": {"arguments": '{"request_'}}]),
        delta(tool_calls=[{"index": 0, "function": {"arguments": 'id": 7}'}}]),
        delta(tool_calls=[{"index": 1, "id": "call_b", "function": {"name": "count_requests", "arguments": "{}"}}]),
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        "[DONE]",
    )

    done = run(build(lambda r: httpx.Response(200, content=body)))[-1]

    assert done.finish_reason == "tool_calls"
    calls = done.message["tool_calls"]
    assert [c["id"] for c in calls] == ["call_a", "call_b"]
    assert json.loads(calls[0]["function"]["arguments"]) == {"request_id": 7}
    assert calls[1]["function"]["name"] == "count_requests"


def test_keeps_reasoning_content_for_providers_that_need_it_back() -> None:
    body = sse(delta(reasoning_content="think"), delta(content="ok"), "[DONE]")

    done = run(build(lambda r: httpx.Response(200, content=body)))[-1]

    assert done.message["reasoning_content"] == "think"


def test_reports_a_length_cut_off() -> None:
    body = sse(delta(content="abc"), {"choices": [{"index": 0, "delta": {}, "finish_reason": "length"}]}, "[DONE]")

    assert run(build(lambda r: httpx.Response(200, content=body)))[-1].finish_reason == "length"


def test_retries_503_then_succeeds() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=sse(delta(content="ok"), "[DONE]"))

    pieces = run(build(handler))

    assert len(calls) == 3
    assert pieces[-1].message["content"] == "ok"


def test_gives_up_after_the_retry_budget() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "0"})

    with pytest.raises(LLMError, match="gave up"):
        run(build(handler, retries=2))

    assert len(calls) == 3


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_does_not_retry_client_errors_and_never_leaks_the_key(status_code: int) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status_code, text="bad key sk-secret-key")

    with pytest.raises(LLMError) as error:
        run(build(handler))

    assert len(calls) == 1
    assert "sk-secret-key" not in str(error.value)


def test_retries_network_errors() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, content=sse(delta(content="ok"), "[DONE]"))

    assert run(build(handler))[-1].message["content"] == "ok"
    assert len(calls) == 2


class BrokenStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield sse(delta(content="partial"))
        raise httpx.ReadError("connection reset")


def test_does_not_restart_a_stream_that_already_sent_text() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, stream=BrokenStream())

    llm = build(handler)
    received: list[Any] = []
    with pytest.raises(LLMError, match="mid-answer"):
        for piece in llm.stream_chat(MESSAGES, TOOLS, time.monotonic() + 5):
            received.append(piece)

    assert [p.text for p in received] == ["partial"]
    assert len(calls) == 1


def test_expired_deadline_raises_timeout_without_calling_the_provider() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, content=sse("[DONE]"))

    with pytest.raises(LLMTimeout):
        run(build(handler), seconds=-1)

    assert calls == []


def test_invalid_json_from_the_provider_is_an_error() -> None:
    with pytest.raises(LLMError, match="invalid JSON"):
        run(build(lambda r: httpx.Response(200, content=sse("{not json"))))


def test_provider_needs_all_three_settings() -> None:
    with pytest.raises(ValueError, match="must all be set"):
        OpenAICompatibleLLM("http://llm.test/v1", "", "some-model")
