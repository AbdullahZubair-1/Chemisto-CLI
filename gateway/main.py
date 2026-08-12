"""FastAPI LLM Gateway.

Public API contract (consumed by chemisto/gateway.py):

    GET    /health
    GET    /models
    POST   /sessions
    GET    /sessions/{chat_id}
    GET    /sessions/{chat_id}/history
    POST   /sessions/{chat_id}/messages
    POST   /sessions/{chat_id}/messages/stream
    DELETE /sessions/{chat_id}/messages

The /stream endpoint returns newline-delimited JSON (application/x-ndjson),
one object per line, of the form:

    {"type": "content", "text": "..."}     zero or more, as tokens arrive
    {"type": "done", "model": "...", "usage": {...}}   exactly one, on success
    {"type": "error", "status_code": 429, "detail": "..."}   instead of "done", on failure

The HTTP status is always 200 once streaming has started (mid-stream
provider errors are signalled in-band via the "error" line) - callers must
check the last line's "type", not just the status code.
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from gateway.config import settings
from gateway.models import (
    ClearResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    HistoryMessage,
    HistoryResponse,
    ModelInfo,
    ModelsResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionInfoResponse,
    Usage,
)
from gateway.openrouter import OpenRouterError, chat_completion, stream_chat_completion
from gateway.ratelimit import MinIntervalThrottle
from gateway.store import ChatSession, store

app = FastAPI(title="Chemisto Gateway", version="0.1.0")
throttle = MinIntervalThrottle(settings.openrouter_min_interval_seconds)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    return ModelsResponse(
        models=[ModelInfo(id=m.id, label=m.label) for m in settings.models],
        default_model=settings.default_model.id,
    )


@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session(payload: CreateSessionRequest) -> CreateSessionResponse:
    model = _resolve_model(payload.model)
    session = store.create(model=model)
    return CreateSessionResponse(chat_id=session.chat_id, model=session.model, created_at=session.created_at)


@app.get("/sessions/{chat_id}", response_model=SessionInfoResponse)
async def get_session(chat_id: str) -> SessionInfoResponse:
    session = _require_session(chat_id)
    return SessionInfoResponse(
        chat_id=session.chat_id,
        model=session.model,
        created_at=session.created_at,
        message_count=len(session.messages),
    )


@app.get("/sessions/{chat_id}/history", response_model=HistoryResponse)
async def get_history(chat_id: str) -> HistoryResponse:
    session = _require_session(chat_id)
    messages = [
        HistoryMessage(index=i, role=m.role, content=m.content)
        for i, m in enumerate(session.messages, start=1)
    ]
    return HistoryResponse(chat_id=session.chat_id, model=session.model, messages=messages)


@app.post("/sessions/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(chat_id: str, payload: SendMessageRequest) -> SendMessageResponse:
    session, api_messages = _prepare_turn(chat_id, payload)

    await throttle.wait()
    try:
        reply, usage = await chat_completion(settings, session.model, api_messages)
    except OpenRouterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    store.append(chat_id, "assistant", reply)

    return SendMessageResponse(chat_id=chat_id, model=session.model, reply=reply, usage=usage)


@app.post("/sessions/{chat_id}/messages/stream")
async def send_message_stream(chat_id: str, payload: SendMessageRequest) -> StreamingResponse:
    session, api_messages = _prepare_turn(chat_id, payload)
    model = session.model

    async def event_stream():
        collected: list[str] = []
        usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        await throttle.wait()
        try:
            async for item in stream_chat_completion(settings, model, api_messages):
                if isinstance(item, str):
                    collected.append(item)
                    yield json.dumps({"type": "content", "text": item}) + "\n"
                else:
                    usage = item
        except OpenRouterError as exc:
            yield json.dumps({"type": "error", "status_code": exc.status_code, "detail": exc.message}) + "\n"
            return

        store.append(chat_id, "assistant", "".join(collected))
        yield json.dumps({"type": "done", "model": model, "usage": usage.model_dump()}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.delete("/sessions/{chat_id}/messages", response_model=ClearResponse)
async def clear_messages(chat_id: str) -> ClearResponse:
    _require_session(chat_id)
    cleared = store.clear_messages(chat_id)
    return ClearResponse(chat_id=chat_id, cleared=cleared)


def _prepare_turn(chat_id: str, payload: SendMessageRequest) -> tuple[ChatSession, list[dict[str, str]]]:
    """Validate/apply an optional model switch, append the user's message,
    and return the resulting session plus the message list to send upstream.
    Shared by both the blocking and streaming /messages endpoints."""
    _require_session(chat_id)

    if payload.model is not None and settings.model_by_id(payload.model) is None:
        raise HTTPException(status_code=400, detail=f"Unknown model id: {payload.model}")
    if payload.model is not None:
        store.set_model(chat_id, payload.model)

    store.append(chat_id, "user", payload.content)
    session = _require_session(chat_id)
    api_messages = [{"role": m.role, "content": m.content} for m in session.messages]
    return session, api_messages


def _resolve_model(model_id: str | None) -> str:
    if model_id is None:
        return settings.default_model.id
    if settings.model_by_id(model_id) is None:
        raise HTTPException(status_code=400, detail=f"Unknown model id: {model_id}")
    return model_id


def _require_session(chat_id: str):
    session = store.get(chat_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No such session: {chat_id}")
    return session
