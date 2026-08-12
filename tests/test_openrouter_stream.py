"""Tests for gateway/openrouter.py's SSE parsing of OpenRouter's streaming
chat completion responses, mocked with respx so no network call is made."""
import httpx
import pytest
import respx

from gateway.config import GatewaySettings, ModelConfig
from gateway.openrouter import OpenRouterError, stream_chat_completion

BASE_URL = "https://openrouter.test/api/v1"


def make_settings() -> GatewaySettings:
    return GatewaySettings(
        openrouter_api_key="test-key",
        openrouter_base_url=BASE_URL,
        openrouter_site_url="https://example.com",
        openrouter_app_name="Chemisto Test",
        openrouter_timeout_seconds=5.0,
        openrouter_min_interval_seconds=0.0,
        host="127.0.0.1",
        port=8000,
        models=[ModelConfig(id="m1", label="Model One")],
    )


@pytest.mark.asyncio
@respx.mock
async def test_stream_yields_content_deltas_then_usage():
    sse_body = (
        'data: {"choices": [{"delta": {"content": "Hel"}}]}\n\n'
        'data: {"choices": [{"delta": {"content": "lo"}}]}\n\n'
        'data: {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})
    )

    settings = make_settings()
    items = []
    async for item in stream_chat_completion(settings, "m1", [{"role": "user", "content": "hi"}]):
        items.append(item)

    content_items = [i for i in items if isinstance(i, str)]
    usage_items = [i for i in items if not isinstance(i, str)]
    assert "".join(content_items) == "Hello"
    assert usage_items[-1].total_tokens == 7


@pytest.mark.asyncio
@respx.mock
async def test_stream_http_error_status_raises_openrouter_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "Rate limited"}})
    )
    settings = make_settings()

    with pytest.raises(OpenRouterError) as exc_info:
        async for _ in stream_chat_completion(settings, "m1", [{"role": "user", "content": "hi"}]):
            pass
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_stream_missing_api_key_raises_before_any_request():
    settings = make_settings()
    settings = GatewaySettings(**{**settings.__dict__, "openrouter_api_key": ""})

    with pytest.raises(OpenRouterError):
        async for _ in stream_chat_completion(settings, "m1", [{"role": "user", "content": "hi"}]):
            pass
