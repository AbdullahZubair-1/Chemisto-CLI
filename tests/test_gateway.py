"""Tests for chemisto/gateway.py's HTTP client, using respx to mock httpx
so these tests never depend on a live gateway or network access."""
import httpx
import pytest
import respx

from chemisto.config import ChemistoSettings
from chemisto.exceptions import (
    GatewayConnectionError,
    GatewayHTTPError,
    GatewayResponseError,
    GatewayTimeoutError,
)
from chemisto.gateway import GatewayClient

BASE_URL = "http://testgateway.local"


def make_settings() -> ChemistoSettings:
    return ChemistoSettings(
        gateway_url=BASE_URL,
        http_timeout_seconds=5.0,
        max_file_size_bytes=1000,
        max_command_output_chars=1000,
        command_timeout_seconds=5.0,
        tree_max_depth=3,
        session_dir=None,
        session_file=None,
    )


@respx.mock
def test_list_models_success():
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [{"id": "m1", "label": "Model One"}],
                "default_model": "m1",
            },
        )
    )
    client = GatewayClient(make_settings())
    models, default = client.list_models()
    assert models[0].id == "m1"
    assert default == "m1"


@respx.mock
def test_create_session_success():
    respx.post(f"{BASE_URL}/sessions").mock(
        return_value=httpx.Response(200, json={"chat_id": "abc", "model": "m1", "created_at": "t"})
    )
    client = GatewayClient(make_settings())
    session = client.create_session()
    assert session.chat_id == "abc"


@respx.mock
def test_send_message_success():
    respx.post(f"{BASE_URL}/sessions/abc/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "chat_id": "abc",
                "model": "m1",
                "reply": "Hello!",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )
    )
    client = GatewayClient(make_settings())
    reply = client.send_message("abc", "hi")
    assert reply.reply == "Hello!"
    assert reply.usage.total_tokens == 3


@respx.mock
def test_get_session_returns_none_on_404():
    respx.get(f"{BASE_URL}/sessions/gone").mock(return_value=httpx.Response(404, json={"detail": "no such session"}))
    client = GatewayClient(make_settings())
    assert client.get_session("gone") is None


@respx.mock
def test_http_error_status_raises_gateway_http_error():
    respx.post(f"{BASE_URL}/sessions/abc/messages").mock(
        return_value=httpx.Response(401, json={"detail": "Missing Authentication header"})
    )
    client = GatewayClient(make_settings())
    with pytest.raises(GatewayHTTPError) as exc_info:
        client.send_message("abc", "hi")
    assert exc_info.value.status_code == 401
    assert "Authentication" in exc_info.value.detail


@respx.mock
def test_connection_error_raises_gateway_connection_error():
    respx.get(f"{BASE_URL}/models").mock(side_effect=httpx.ConnectError("refused"))
    client = GatewayClient(make_settings())
    with pytest.raises(GatewayConnectionError):
        client.list_models()


@respx.mock
def test_timeout_raises_gateway_timeout_error():
    respx.get(f"{BASE_URL}/models").mock(side_effect=httpx.TimeoutException("timed out"))
    client = GatewayClient(make_settings())
    with pytest.raises(GatewayTimeoutError):
        client.list_models()


@respx.mock
def test_invalid_json_raises_gateway_response_error():
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "application/json"})
    )
    client = GatewayClient(make_settings())
    with pytest.raises(GatewayResponseError):
        client.list_models()


@respx.mock
def test_clear_session_success():
    respx.delete(f"{BASE_URL}/sessions/abc/messages").mock(
        return_value=httpx.Response(200, json={"chat_id": "abc", "cleared": True})
    )
    client = GatewayClient(make_settings())
    assert client.clear_session("abc") is True
