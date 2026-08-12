import json
from pathlib import Path
from unittest.mock import MagicMock

from chemisto.config import ChemistoSettings
from chemisto.gateway import SessionInfo
from chemisto.session import (
    load_local_session,
    resume_or_create_session,
    save_local_session,
    start_new_session,
)
from chemisto.session import LocalSession


def make_settings(tmp_path: Path) -> ChemistoSettings:
    session_dir = tmp_path / ".ats-ai"
    return ChemistoSettings(
        gateway_url="http://127.0.0.1:8000",
        http_timeout_seconds=5.0,
        max_file_size_bytes=1000,
        max_command_output_chars=1000,
        command_timeout_seconds=5.0,
        tree_max_depth=3,
        session_dir=session_dir,
        session_file=session_dir / "session.json",
    )


def test_save_and_load_round_trip(tmp_path):
    settings = make_settings(tmp_path)
    save_local_session(settings, LocalSession(chat_id="abc123", model="m1"))

    loaded = load_local_session(settings)
    assert loaded.chat_id == "abc123"
    assert loaded.model == "m1"


def test_load_missing_session_file_returns_none(tmp_path):
    settings = make_settings(tmp_path)
    assert load_local_session(settings) is None


def test_load_malformed_session_file_returns_none(tmp_path):
    settings = make_settings(tmp_path)
    settings.session_dir.mkdir(parents=True)
    settings.session_file.write_text("not json", encoding="utf-8")
    assert load_local_session(settings) is None


def test_load_session_missing_fields_returns_none(tmp_path):
    settings = make_settings(tmp_path)
    settings.session_dir.mkdir(parents=True)
    settings.session_file.write_text(json.dumps({"chat_id": "abc"}), encoding="utf-8")
    assert load_local_session(settings) is None


def test_resume_creates_new_session_when_none_local(tmp_path):
    settings = make_settings(tmp_path)
    client = MagicMock()
    client.create_session.return_value = SessionInfo(chat_id="new1", model="m1", created_at="t")

    session, resumed = resume_or_create_session(settings, client)

    assert resumed is False
    assert session.chat_id == "new1"
    client.create_session.assert_called_once()


def test_resume_uses_existing_when_gateway_confirms_it(tmp_path):
    settings = make_settings(tmp_path)
    save_local_session(settings, LocalSession(chat_id="existing1", model="m1"))
    client = MagicMock()
    client.get_session.return_value = SessionInfo(chat_id="existing1", model="m1", created_at="t")

    session, resumed = resume_or_create_session(settings, client)

    assert resumed is True
    assert session.chat_id == "existing1"
    client.create_session.assert_not_called()


def test_resume_creates_new_session_when_gateway_forgot_it(tmp_path):
    settings = make_settings(tmp_path)
    save_local_session(settings, LocalSession(chat_id="gone", model="m1"))
    client = MagicMock()
    client.get_session.return_value = None
    client.create_session.return_value = SessionInfo(chat_id="fresh", model="m1", created_at="t")

    session, resumed = resume_or_create_session(settings, client)

    assert resumed is False
    assert session.chat_id == "fresh"


def test_start_new_session_overwrites_local_file(tmp_path):
    settings = make_settings(tmp_path)
    save_local_session(settings, LocalSession(chat_id="old", model="m1"))
    client = MagicMock()
    client.create_session.return_value = SessionInfo(chat_id="new2", model="m2", created_at="t")

    session = start_new_session(settings, client, model="m2")

    assert session.chat_id == "new2"
    reloaded = load_local_session(settings)
    assert reloaded.chat_id == "new2"
