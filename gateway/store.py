"""In-process session store.

The gateway is intentionally stateless across restarts for this MVP: chat
history lives in memory only. This keeps the service simple and avoids
inventing a persistence layer nobody asked for. The CLI is written to
tolerate a missing chat_id (e.g. after a gateway restart) by transparently
starting a new session - see chemisto/session.py.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatSession:
    chat_id: str
    model: str
    created_at: str
    messages: list[ChatMessage] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def create(self, model: str) -> ChatSession:
        chat_id = uuid.uuid4().hex[:12]
        session = ChatSession(
            chat_id=chat_id,
            model=model,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._sessions[chat_id] = session
        return session

    def get(self, chat_id: str) -> ChatSession | None:
        with self._lock:
            return self._sessions.get(chat_id)

    def clear_messages(self, chat_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None:
                return False
            session.messages.clear()
            return True

    def append(self, chat_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None:
                raise KeyError(chat_id)
            session.messages.append(ChatMessage(role=role, content=content))

    def set_model(self, chat_id: str, model: str) -> None:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None:
                raise KeyError(chat_id)
            session.model = model


store = SessionStore()
