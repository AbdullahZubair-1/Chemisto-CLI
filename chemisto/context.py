"""Context manager: builds the tool-supplied context that is prepended to
LLM requests, keeping it clearly separated from the user's own words.

Only explicit user commands (/file, /run) ever populate this context -
Chemisto never reads the filesystem or executes anything on its own
initiative. Context is held in memory only and is wiped by /new and
/clear so nothing leaks across sessions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from chemisto.config import ChemistoSettings
from chemisto.exceptions import FileContextError

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".txt": "text",
}


@dataclass
class FileContext:
    path: str
    language: str
    content: str


@dataclass
class CommandContext:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass
class ContextManager:
    files: list[FileContext] = field(default_factory=list)
    commands: list[CommandContext] = field(default_factory=list)

    def add_file(self, path: str, settings: ChemistoSettings) -> FileContext:
        file_path = Path(path)

        if not file_path.exists():
            raise FileContextError(f"File not found: {path}")
        if file_path.is_dir():
            raise FileContextError(f"Expected a file, but got a directory: {path}")

        try:
            size = file_path.stat().st_size
        except OSError as exc:
            raise FileContextError(f"Could not stat file: {path} ({exc})") from exc

        if size > settings.max_file_size_bytes:
            raise FileContextError(
                f"File too large ({size:,} bytes > {settings.max_file_size_bytes:,} byte limit): {path}"
            )

        try:
            raw = file_path.read_bytes()
        except PermissionError as exc:
            raise FileContextError(f"Permission denied reading file: {path}") from exc
        except OSError as exc:
            raise FileContextError(f"Could not read file: {path} ({exc})") from exc

        if b"\x00" in raw:
            raise FileContextError(f"Refusing to add binary file as context: {path}")

        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileContextError(f"File is not valid UTF-8 text: {path} ({exc})") from exc

        language = _LANGUAGE_BY_EXTENSION.get(file_path.suffix.lower(), "text")
        context = FileContext(path=str(path), language=language, content=content)
        self.files.append(context)
        return context

    def add_command_result(
        self, command: str, exit_code: int, stdout: str, stderr: str, timed_out: bool = False
    ) -> CommandContext:
        context = CommandContext(
            command=command, exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=timed_out
        )
        self.commands.append(context)
        return context

    def clear(self) -> None:
        self.files.clear()
        self.commands.clear()

    def is_empty(self) -> bool:
        return not self.files and not self.commands

    def build_prompt(self, user_request: str) -> str:
        """Combine any accumulated tool context with the user's own request,
        using explicit delimiters so the LLM cannot mistake tool output for a
        direct user instruction."""
        blocks: list[str] = []

        for file_ctx in self.files:
            blocks.append(
                "[FILE CONTEXT]\n"
                f"Path: {file_ctx.path}\n"
                f"Language: {file_ctx.language}\n\n"
                f"```{file_ctx.language}\n{file_ctx.content}\n```\n"
                "[END FILE CONTEXT]"
            )

        for cmd_ctx in self.commands:
            status = "TIMED OUT" if cmd_ctx.timed_out else str(cmd_ctx.exit_code)
            blocks.append(
                "[COMMAND CONTEXT]\n"
                f"Command: {cmd_ctx.command}\n"
                f"Exit code: {status}\n\n"
                f"STDOUT:\n{cmd_ctx.stdout or '(empty)'}\n\n"
                f"STDERR:\n{cmd_ctx.stderr or '(empty)'}\n"
                "[END COMMAND CONTEXT]"
            )

        if not blocks:
            return user_request

        return "\n\n".join(blocks) + f"\n\nUSER REQUEST:\n{user_request}"


def detect_language(path: str) -> str:
    return _LANGUAGE_BY_EXTENSION.get(Path(path).suffix.lower(), "text")
