"""Directory inspection helpers used by /ls and /tree.

Both stay local, bounded operations - they never send output to the LLM
by themselves. If the user later references the listing in a message,
that message is sent as ordinary text, not as injected context.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ats-ai",
}

MAX_LS_ENTRIES = 200


@dataclass
class DirEntry:
    name: str
    is_dir: bool
    size: int | None


def list_directory(path: str = ".") -> list[DirEntry]:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name in IGNORED_DIR_NAMES:
            continue
        try:
            size = None if child.is_dir() else child.stat().st_size
        except OSError:
            size = None
        entries.append(DirEntry(name=child.name, is_dir=child.is_dir(), size=size))

    return entries[:MAX_LS_ENTRIES]


def build_tree_lines(path: str = ".", max_depth: int = 3) -> list[str]:
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    lines = [root.name or str(root)]
    _walk(root, prefix="", depth=0, max_depth=max_depth, lines=lines)
    return lines


def _walk(directory: Path, prefix: str, depth: int, max_depth: int, lines: list[str]) -> None:
    if depth >= max_depth:
        return

    try:
        children = [
            c for c in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            if c.name not in IGNORED_DIR_NAMES
        ]
    except OSError:
        return

    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        connector = "└── " if is_last else "├── "
        suffix = "/" if child.is_dir() else ""
        lines.append(f"{prefix}{connector}{child.name}{suffix}")
        if child.is_dir():
            extension = "    " if is_last else "│   "
            _walk(child, prefix + extension, depth + 1, max_depth, lines)
