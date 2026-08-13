"""Tests for gateway/store.py's on-disk chat persistence: each chat gets its
own JSON file, named after a topic once set, and reloads correctly from a
fresh SessionStore instance (simulating a gateway restart)."""
import dataclasses
import json

import pytest

from gateway import store as store_module
from gateway.store import SessionStore, _slugify


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    test_settings = dataclasses.replace(store_module.settings, sessions_dir=tmp_path)
    monkeypatch.setattr(store_module, "settings", test_settings)
    return tmp_path


def test_slugify_basic():
    assert _slugify("Explain Python Decorators!") == "explain-python-decorators"


def test_slugify_empty_falls_back_to_untitled():
    assert _slugify("!!! ??? ...") == "untitled"


def test_create_persists_an_untitled_file(sessions_dir):
    store = SessionStore()
    session = store.create(model="m1")

    files = list(sessions_dir.glob("*.json"))
    assert len(files) == 1
    assert files[0].name == f"untitled-{session.chat_id}.json"


def test_append_updates_the_persisted_file(sessions_dir):
    store = SessionStore()
    session = store.create(model="m1")
    store.append(session.chat_id, "user", "hello")

    data = json.loads(session.file_path.read_text(encoding="utf-8"))
    assert data["messages"] == [{"role": "user", "content": "hello"}]


def test_set_title_renames_the_file(sessions_dir):
    store = SessionStore()
    session = store.create(model="m1")
    store.append(session.chat_id, "user", "Explain decorators")
    old_path = session.file_path

    store.set_title(session.chat_id, "Explain Python Decorators")

    new_path = store.get(session.chat_id).file_path
    assert new_path.name == f"explain-python-decorators-{session.chat_id}.json"
    assert not old_path.exists()
    assert new_path.exists()


def test_mark_title_requested_only_returns_true_once(sessions_dir):
    store = SessionStore()
    session = store.create(model="m1")

    assert store.mark_title_requested(session.chat_id) is True
    assert store.mark_title_requested(session.chat_id) is False


def test_reload_from_disk_restores_sessions(sessions_dir):
    store = SessionStore()
    session = store.create(model="m1")
    store.append(session.chat_id, "user", "hi")
    store.append(session.chat_id, "assistant", "hello back")
    store.set_title(session.chat_id, "Greeting chat")

    reloaded = SessionStore()
    restored = reloaded.get(session.chat_id)

    assert restored is not None
    assert restored.model == "m1"
    assert restored.title == "Greeting chat"
    assert [m.content for m in restored.messages] == ["hi", "hello back"]


def test_clear_messages_persists_emptied_file(sessions_dir):
    store = SessionStore()
    session = store.create(model="m1")
    store.append(session.chat_id, "user", "hi")

    store.clear_messages(session.chat_id)

    data = json.loads(session.file_path.read_text(encoding="utf-8"))
    assert data["messages"] == []
