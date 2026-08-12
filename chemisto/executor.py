"""Subprocess execution for /run.

This is the ONLY place a shell command is ever executed, and it only
runs in direct response to a user typing /run <command>. The LLM is
never given the ability to trigger this path - it can only see the
captured result afterward as command context.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from chemisto.exceptions import CommandExecutionError


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def run_command(command: str, timeout_seconds: float, max_output_chars: int) -> CommandResult:
    if not command.strip():
        raise CommandExecutionError("No command provided.")

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _truncate(_decode(exc.stdout), max_output_chars)
        stderr = _truncate(_decode(exc.stderr), max_output_chars)
        return CommandResult(
            command=command, exit_code=-1, stdout=stdout, stderr=stderr, timed_out=True
        )
    except OSError as exc:
        raise CommandExecutionError(f"Failed to execute command: {exc}") from exc

    stdout = _truncate(completed.stdout or "", max_output_chars)
    stderr = _truncate(completed.stderr or "", max_output_chars)
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
    )


def _decode(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n... [output truncated, {omitted} characters omitted]"
