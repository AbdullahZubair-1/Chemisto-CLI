"""Pydantic v2 request/response schemas for the gateway's public API contract.

The CLI's HTTP client (chemisto/gateway.py) is written against exactly
these shapes - the two sides of the contract are kept in this one repo
so they cannot drift silently.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["user", "assistant"]


class ModelInfo(BaseModel):
    id: str
    label: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str


class CreateSessionRequest(BaseModel):
    model: str | None = Field(default=None, description="Model id to start the session with; defaults to the gateway's default model.")


class CreateSessionResponse(BaseModel):
    chat_id: str
    model: str
    created_at: str


class SessionInfoResponse(BaseModel):
    chat_id: str
    model: str
    created_at: str
    message_count: int


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    model: str | None = Field(default=None, description="Override the model for this turn; also becomes the session's new active model.")


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class SendMessageResponse(BaseModel):
    chat_id: str
    model: str
    reply: str
    usage: Usage


class HistoryMessage(BaseModel):
    index: int
    role: Role
    content: str


class HistoryResponse(BaseModel):
    chat_id: str
    model: str
    messages: list[HistoryMessage]


class ClearResponse(BaseModel):
    chat_id: str
    cleared: bool


class ErrorResponse(BaseModel):
    detail: str
