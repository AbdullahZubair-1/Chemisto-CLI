from pathlib import Path

import pytest

from chemisto.config import ChemistoSettings
from chemisto.context import ContextManager
from chemisto.exceptions import FileContextError


def make_settings(tmp_path: Path, max_file_size_bytes: int = 1000) -> ChemistoSettings:
    session_dir = tmp_path / ".ats-ai"
    return ChemistoSettings(
        gateway_url="http://127.0.0.1:8000",
        http_timeout_seconds=5.0,
        max_file_size_bytes=max_file_size_bytes,
        max_command_output_chars=1000,
        command_timeout_seconds=5.0,
        tree_max_depth=3,
        session_dir=session_dir,
        session_file=session_dir / "session.json",
    )


def test_add_valid_python_file_detects_language(tmp_path):
    file_path = tmp_path / "auth.py"
    file_path.write_text("def login():\n    pass\n", encoding="utf-8")
    manager = ContextManager()

    ctx = manager.add_file(str(file_path), make_settings(tmp_path))

    assert ctx.language == "python"
    assert "def login" in ctx.content
    assert len(manager.files) == 1


def test_add_missing_file_raises(tmp_path):
    manager = ContextManager()
    with pytest.raises(FileContextError, match="not found"):
        manager.add_file(str(tmp_path / "missing.py"), make_settings(tmp_path))


def test_add_directory_raises(tmp_path):
    manager = ContextManager()
    with pytest.raises(FileContextError, match="directory"):
        manager.add_file(str(tmp_path), make_settings(tmp_path))


def test_add_binary_file_raises(tmp_path):
    file_path = tmp_path / "image.bin"
    file_path.write_bytes(b"\x00\x01\x02binarydata")
    manager = ContextManager()
    with pytest.raises(FileContextError, match="binary"):
        manager.add_file(str(file_path), make_settings(tmp_path))


def test_add_oversized_file_raises(tmp_path):
    file_path = tmp_path / "big.txt"
    file_path.write_text("x" * 2000, encoding="utf-8")
    manager = ContextManager()
    with pytest.raises(FileContextError, match="too large"):
        manager.add_file(str(file_path), make_settings(tmp_path, max_file_size_bytes=100))


def test_multiple_files_all_included_in_prompt(tmp_path):
    file_a = tmp_path / "a.py"
    file_a.write_text("A = 1", encoding="utf-8")
    file_b = tmp_path / "b.js"
    file_b.write_text("const b = 2;", encoding="utf-8")
    manager = ContextManager()
    settings = make_settings(tmp_path)

    manager.add_file(str(file_a), settings)
    manager.add_file(str(file_b), settings)
    prompt = manager.build_prompt("Explain both files.")

    assert "a.py" in prompt
    assert "b.js" in prompt
    assert "USER REQUEST:\nExplain both files." in prompt
    assert prompt.index("[FILE CONTEXT]") < prompt.index("USER REQUEST:")


def test_plain_message_with_no_context_is_unchanged(tmp_path):
    manager = ContextManager()
    prompt = manager.build_prompt("Just a question.")
    assert prompt == "Just a question."


def test_command_context_included_with_delimiters():
    manager = ContextManager()
    manager.add_command_result("pytest tests/", exit_code=1, stdout="1 failed", stderr="AssertionError")
    prompt = manager.build_prompt("Why did this fail?")

    assert "[COMMAND CONTEXT]" in prompt
    assert "[END COMMAND CONTEXT]" in prompt
    assert "pytest tests/" in prompt
    assert "AssertionError" in prompt


def test_clear_removes_all_context():
    manager = ContextManager()
    manager.add_command_result("echo hi", exit_code=0, stdout="hi", stderr="")
    assert manager.is_empty() is False
    manager.clear()
    assert manager.is_empty() is True
    assert manager.build_prompt("hello") == "hello"
