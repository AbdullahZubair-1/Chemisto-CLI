"""Tests for command execution (/run) and directory helpers (/ls, /tree)."""
import sys

import pytest

from chemisto.directory import build_tree_lines, list_directory
from chemisto.exceptions import CommandExecutionError
from chemisto.executor import run_command


def test_run_successful_command_captures_stdout():
    command = f'"{sys.executable}" -c "print(1)"'
    result = run_command(command, timeout_seconds=10, max_output_chars=1000)
    assert result.exit_code == 0
    assert "1" in result.stdout
    assert result.timed_out is False


def test_run_failing_command_captures_stderr_and_exit_code():
    command = f'"{sys.executable}" -c "import sys; sys.stderr.write(\'boom\'); sys.exit(3)"'
    result = run_command(command, timeout_seconds=10, max_output_chars=1000)
    assert result.exit_code == 3
    assert "boom" in result.stderr


def test_run_command_times_out():
    command = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    result = run_command(command, timeout_seconds=0.5, max_output_chars=1000)
    assert result.timed_out is True


def test_run_output_is_truncated_to_limit():
    command = f'"{sys.executable}" -c "print(\'x\' * 5000)"'
    result = run_command(command, timeout_seconds=10, max_output_chars=100)
    assert len(result.stdout) < 5000
    assert "truncated" in result.stdout


def test_run_empty_command_raises():
    with pytest.raises(CommandExecutionError):
        run_command("   ", timeout_seconds=5, max_output_chars=100)


def test_list_directory_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list_directory(str(tmp_path / "nope"))


def test_list_directory_file_instead_of_dir_raises(tmp_path):
    file_path = tmp_path / "f.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        list_directory(str(file_path))


def test_list_directory_skips_ignored_dirs(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "readme.md").write_text("x", encoding="utf-8")

    entries = list_directory(str(tmp_path))
    names = {e.name for e in entries}
    assert "__pycache__" not in names
    assert "src" in names
    assert "readme.md" in names


def test_build_tree_lines_respects_max_depth(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (nested / "deep.txt").write_text("x", encoding="utf-8")

    lines = build_tree_lines(str(tmp_path), max_depth=1)
    joined = "\n".join(lines)
    assert "a/" in joined
    assert "deep.txt" not in joined
