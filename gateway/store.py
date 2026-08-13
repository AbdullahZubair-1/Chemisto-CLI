"""Session store with on-disk persistence.

Every chat is mirrored to its own JSON file under `settings.sessions_dir`,
named after a short topic slug plus the chat_id (e.g.
`explain-python-decorators-a1b2c3d4e5f6.json`) so conversations survive a
gateway restart and are easy to browse by topic. The topic itself is filled
in asynchronously (see gateway/main.py) once the AI has generated a short
title for the chat - until then, the file is named `untitled-{chat_id}`.

File writes are small (a handful of KB at most for a chat session) and done
synchronously under the same lock as the in-memory mutation, which briefly
blocks the event loop but keeps this module simple - there is no need for
a database or async file I/O for a single-user local tool like this.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from gateway.config import settings


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
    title: str | None = None
    title_requested: bool = False
    file_path: Path | None = field(default=None, repr=False)


def _slugify(text: str, max_words: int = 6, max_length: int = 50) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())[:max_words]
    slug = "-".join(words)
    return slug[:max_length].rstrip("-") or "untitled"


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def create(self, model: str) -> ChatSession:
        chat_id = uuid.uuid4().hex[:12]
        session = ChatSession(
            chat_id=chat_id,
            model=model,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._sessions[chat_id] = session
            self._persist(session)
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
            self._persist(session)
            return True

    def append(self, chat_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None:
                raise KeyError(chat_id)
            session.messages.append(ChatMessage(role=role, content=content))
            self._persist(session)

    def set_model(self, chat_id: str, model: str) -> None:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None:
                raise KeyError(chat_id)
            session.model = model
            self._persist(session)

    def set_title(self, chat_id: str, title: str) -> None:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None:
                return
            old_path = session.file_path
            session.title = title
            self._persist(session)
            if old_path is not None and old_path != session.file_path and old_path.exists():
                old_path.unlink(missing_ok=True)

    def mark_title_requested(self, chat_id: str) -> bool:
        """Returns True the first time it's called for a chat, False after -
        lets the caller fire the title-generation request exactly once."""
        with self._lock:
            session = self._sessions.get(chat_id)
            if session is None or session.title_requested:
                return False
            session.title_requested = True
            return True

    def _persist(self, session: ChatSession) -> None:
        slug = _slugify(session.title) if session.title else "untitled"
        new_path = settings.sessions_dir / f"{slug}-{session.chat_id}.json"

        data = {
            "chat_id": session.chat_id,
            "model": session.model,
            "created_at": session.created_at,
            "title": session.title,
            "messages": [asdict(m) for m in session.messages],
        }
        new_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        if session.file_path is not None and session.file_path != new_path and session.file_path.exists():
            session.file_path.unlink(missing_ok=True)
        session.file_path = new_path

    def _load_from_disk(self) -> None:
        for path in settings.sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                session = ChatSession(
                    chat_id=data["chat_id"],
                    model=data["model"],
                    created_at=data["created_at"],
                    messages=[ChatMessage(**m) for m in data.get("messages", [])],
                    title=data.get("title"),
                    title_requested=bool(data.get("title")),
                    file_path=path,
                )
            except (OSError, ValueError, KeyError):
                continue
            self._sessions[session.chat_id] = session


store = SessionStore()
