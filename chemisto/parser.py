"""Centralized, testable command parser.

Any input starting with "/" is a command; everything else is a plain
message destined for the LLM. Kept as pure functions with no I/O so it
is trivial to unit test.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedInput:
    is_command: bool
    command: str | None
    argument: str
    raw: str


def parse_input(raw: str) -> ParsedInput:
    text = raw.strip()

    if not text.startswith("/"):
        return ParsedInput(is_command=False, command=None, argument=text, raw=raw)

    body = text[1:]
    if not body:
        return ParsedInput(is_command=True, command="", argument="", raw=raw)

    parts = body.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""
    return ParsedInput(is_command=True, command=command, argument=argument, raw=raw)


def is_known_command(command: str) -> bool:
    # Imported lazily so this module stays free of I/O-heavy dependencies
    # (rich, httpx, ...) - commands.COMMAND_HANDLERS is the single source of
    # truth for which command names actually exist.
    from chemisto.commands import COMMAND_HANDLERS

    return command in COMMAND_HANDLERS
