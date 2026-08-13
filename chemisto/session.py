"""Local session persistence.

Chemisto keeps a tiny local file (~/.ats-ai/session.json) recording only
the active chat_id and model - never credentials. On startup this file is
used to resume the previous conversation via the gateway. The gateway
itself persists full chat history to disk (see gateway/store.py) and
reloads it on startup, so this normally succeeds even across a gateway
restart; if the chat_id is genuinely unrecognized (e.g. its file was
deleted), a fresh session is created transparently instead.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from chemisto.config import ChemistoSettings
from chemisto.exceptions import SessionError
from chemisto.gateway import GatewayClient


@dataclass
class LocalSession:
    chat_id: str
    model: str

    def to_dict(self) -> dict:
        return {"chat_id": self.chat_id, "model": self.model}


def load_local_session(settings: ChemistoSettings) -> LocalSession | None:
    if not settings.session_file.exists():
        return None
    try:
        raw = settings.session_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise SessionError(f"Could not read session file: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    chat_id = data.get("chat_id")
    model = data.get("model")
    if not chat_id or not model:
        return None
    return LocalSession(chat_id=chat_id, model=model)


def save_local_session(settings: ChemistoSettings, session: LocalSession) -> None:
    try:
        settings.session_dir.mkdir(parents=True, exist_ok=True)
        settings.session_file.write_text(
            json.dumps(session.to_dict(), indent=2), encoding="utf-8"
        )
    except OSError as exc:
        raise SessionError(f"Could not write session file: {exc}") from exc


def resume_or_create_session(
    settings: ChemistoSettings, client: GatewayClient
) -> tuple[LocalSession, bool]:
    """Return (session, resumed). resumed is False when a new session was created."""
    local = load_local_session(settings)
    if local is not None:
        remote = client.get_session(local.chat_id)
        if remote is not None:
            return LocalSession(chat_id=remote.chat_id, model=remote.model), True

    remote = client.create_session()
    session = LocalSession(chat_id=remote.chat_id, model=remote.model)
    save_local_session(settings, session)
    return session, False


def start_new_session(
    settings: ChemistoSettings, client: GatewayClient, model: str | None = None
) -> LocalSession:
    remote = client.create_session(model=model)
    session = LocalSession(chat_id=remote.chat_id, model=remote.model)
    save_local_session(settings, session)
    return session
