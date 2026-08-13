"""Thin async client around OpenRouter's chat completions endpoint.

This is the only module in the whole project allowed to hold the
OpenRouter API key. It exists so gateway/main.py stays focused on HTTP
routing instead of provider details.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from gateway.config import GatewaySettings
from gateway.models import Usage


class OpenRouterError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _require_api_key(settings: GatewaySettings) -> None:
    if not settings.openrouter_api_key:
        raise OpenRouterError(500, "OPENROUTER_API_KEY is not configured on the gateway.")


def _headers(settings: GatewaySettings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.openrouter_site_url,
        "X-Title": settings.openrouter_app_name,
    }


def _usage_from_dict(data: dict | None) -> Usage:
    data = data or {}
    return Usage(
        prompt_tokens=data.get("prompt_tokens", 0),
        completion_tokens=data.get("completion_tokens", 0),
        total_tokens=data.get("total_tokens", 0),
    )


async def chat_completion(
    settings: GatewaySettings,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str, Usage]:
    _require_api_key(settings)
    payload = {"model": model, "messages": messages}

    try:
        async with httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=_headers(settings),
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise OpenRouterError(504, "Timed out waiting for OpenRouter.") from exc
    except httpx.RequestError as exc:
        raise OpenRouterError(502, f"Could not reach OpenRouter: {exc}") from exc

    if response.status_code >= 400:
        raise OpenRouterError(response.status_code, _extract_error_detail(response))

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenRouterError(502, "OpenRouter returned an invalid JSON response.") from exc

    try:
        reply = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError(502, "OpenRouter returned an unexpected response shape.") from exc

    return reply, _usage_from_dict(data.get("usage"))


async def generate_title(settings: GatewaySettings, model: str, first_message: str) -> str:
    """Ask the model for a short topic title for a new chat, used to name
    its persisted JSON file (see gateway/store.py). Reuses chat_completion
    rather than its own HTTP call - this is just a differently-prompted
    completion, not a different API."""
    prompt = (
        "Summarize the following request in 3 to 6 words, suitable as a short "
        "file name. Reply with only those words - no punctuation, no quotes, "
        "no explanation.\n\nRequest:\n" + first_message
    )
    reply, _usage = await chat_completion(settings, model, [{"role": "user", "content": prompt}])
    return reply.strip()


async def stream_chat_completion(
    settings: GatewaySettings,
    model: str,
    messages: list[dict[str, str]],
) -> AsyncIterator[str | Usage]:
    """Stream a chat completion as it arrives.

    Yields each content delta as a plain string as soon as it arrives, and
    yields a final `Usage` object once the stream ends (OpenRouter reports
    token usage in the last chunk when `stream_options.include_usage` is
    set). Callers distinguish the two by type.
    """
    _require_api_key(settings)
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    try:
        async with httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{settings.openrouter_base_url}/chat/completions",
                headers=_headers(settings),
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise OpenRouterError(response.status_code, _extract_error_detail(response))

                usage = _usage_from_dict(None)
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except ValueError:
                        continue

                    choices = chunk.get("choices") or []
                    if choices:
                        content = (choices[0].get("delta") or {}).get("content")
                        if content:
                            yield content

                    if chunk.get("usage"):
                        usage = _usage_from_dict(chunk["usage"])
                yield usage
    except httpx.TimeoutException as exc:
        raise OpenRouterError(504, "Timed out waiting for OpenRouter.") from exc
    except httpx.RequestError as exc:
        raise OpenRouterError(502, f"Could not reach OpenRouter: {exc}") from exc


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        message = data.get("error", {}).get("message") or data.get("detail")
        if message:
            return str(message)
    except ValueError:
        pass
    return f"OpenRouter request failed with status {response.status_code}."
