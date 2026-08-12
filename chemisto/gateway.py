"""HTTP client for the Chemisto FastAPI gateway.

This is the only module that speaks HTTP to the gateway. It mirrors the
exact contract defined in gateway/main.py and gateway/models.py - no
endpoint or payload shape here is invented independently of that
contract.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator

import httpx

from chemisto.config import ChemistoSettings
from chemisto.exceptions import (
    GatewayConnectionError,
    GatewayError,
    GatewayHTTPError,
    GatewayResponseError,
    GatewayTimeoutError,
)


@dataclass
class ModelInfo:
    id: str
    label: str


@dataclass
class SessionInfo:
    chat_id: str
    model: str
    created_at: str


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class MessageReply:
    chat_id: str
    model: str
    reply: str
    usage: Usage


@dataclass
class HistoryEntry:
    index: int
    role: str
    content: str


class GatewayClient:
    def __init__(self, settings: ChemistoSettings) -> None:
        self._settings = settings

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        url = f"{self._settings.gateway_url}{path}"
        try:
            response = httpx.request(
                method, url, json=json, timeout=self._settings.http_timeout_seconds
            )
        except httpx.HTTPError as exc:
            raise _translate_httpx_error(exc) from exc

        if response.status_code >= 400:
            detail = _extract_detail(response)
            raise GatewayHTTPError(response.status_code, detail)

        try:
            return response.json()
        except ValueError as exc:
            raise GatewayResponseError(
                "The gateway returned a response that could not be parsed."
            ) from exc

    def list_models(self) -> tuple[list[ModelInfo], str]:
        data = self._request("GET", "/models")
        models = [ModelInfo(id=m["id"], label=m["label"]) for m in data["models"]]
        return models, data["default_model"]

    def create_session(self, model: str | None = None) -> SessionInfo:
        payload = {"model": model} if model else {}
        data = self._request("POST", "/sessions", json=payload)
        return SessionInfo(chat_id=data["chat_id"], model=data["model"], created_at=data["created_at"])

    def get_session(self, chat_id: str) -> SessionInfo | None:
        try:
            data = self._request("GET", f"/sessions/{chat_id}")
        except GatewayHTTPError as exc:
            if exc.status_code == 404:
                return None
            raise
        return SessionInfo(chat_id=data["chat_id"], model=data["model"], created_at=data["created_at"])

    def send_message(self, chat_id: str, content: str, model: str | None = None) -> MessageReply:
        payload: dict = {"content": content}
        if model:
            payload["model"] = model
        data = self._request("POST", f"/sessions/{chat_id}/messages", json=payload)
        usage = Usage(**data["usage"])
        return MessageReply(chat_id=data["chat_id"], model=data["model"], reply=data["reply"], usage=usage)

    def stream_message(
        self, chat_id: str, content: str, model: str | None = None
    ) -> Iterator[dict]:
        """Stream a reply as newline-delimited JSON events: {"type": "content", "text": ...},
        then a single {"type": "done", ...} event terminating the stream. A mid-stream
        provider error (in-band {"type": "error", ...}) is raised here as GatewayHTTPError,
        same as every other error path, so callers only ever need to catch exceptions - see
        gateway/main.py's module docstring for the exact event contract."""
        url = f"{self._settings.gateway_url}/sessions/{chat_id}/messages/stream"
        payload: dict = {"content": content}
        if model:
            payload["model"] = model

        try:
            with httpx.stream(
                "POST", url, json=payload, timeout=self._settings.http_timeout_seconds
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    raise GatewayHTTPError(response.status_code, _extract_detail(response))

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "error":
                        raise GatewayHTTPError(
                            event.get("status_code", 502), event.get("detail", "Unknown error from gateway.")
                        )
                    yield event
        except httpx.HTTPError as exc:
            raise _translate_httpx_error(exc) from exc

    def get_history(self, chat_id: str) -> tuple[str, list[HistoryEntry]]:
        data = self._request("GET", f"/sessions/{chat_id}/history")
        entries = [HistoryEntry(index=m["index"], role=m["role"], content=m["content"]) for m in data["messages"]]
        return data["model"], entries

    def clear_session(self, chat_id: str) -> bool:
        data = self._request("DELETE", f"/sessions/{chat_id}/messages")
        return bool(data.get("cleared", False))


def _translate_httpx_error(exc: httpx.HTTPError) -> GatewayError:
    if isinstance(exc, httpx.ConnectError):
        return GatewayConnectionError("Unable to connect to the Chemisto gateway. Is it running?")
    if isinstance(exc, httpx.TimeoutException):
        return GatewayTimeoutError("The Chemisto gateway did not respond in time.")
    return GatewayConnectionError(f"Gateway request failed: {exc}")


def _extract_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        detail = data.get("detail")
        if detail:
            return str(detail)
    except ValueError:
        pass
    return f"Gateway request failed with status {response.status_code}."
