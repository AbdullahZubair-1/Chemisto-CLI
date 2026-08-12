"""Central configuration for the Chemisto CLI client.

The CLI never holds OpenRouter credentials - only the gateway URL and
client-side limits (file size, command timeout, output caps) live here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ChemistoSettings:
    gateway_url: str
    http_timeout_seconds: float
    max_file_size_bytes: int
    max_command_output_chars: int
    command_timeout_seconds: float
    tree_max_depth: int
    session_dir: Path
    session_file: Path


def load_settings() -> ChemistoSettings:
    session_dir = Path(os.getenv("CHEMISTO_SESSION_DIR", str(Path.home() / ".ats-ai")))
    return ChemistoSettings(
        gateway_url=os.getenv("CHEMISTO_GATEWAY_URL", "http://127.0.0.1:8000").rstrip("/"),
        http_timeout_seconds=float(os.getenv("CHEMISTO_HTTP_TIMEOUT_SECONDS", "65")),
        max_file_size_bytes=int(os.getenv("CHEMISTO_MAX_FILE_SIZE_BYTES", "200000")),
        max_command_output_chars=int(os.getenv("CHEMISTO_MAX_COMMAND_OUTPUT_CHARS", "8000")),
        command_timeout_seconds=float(os.getenv("CHEMISTO_COMMAND_TIMEOUT_SECONDS", "30")),
        tree_max_depth=int(os.getenv("CHEMISTO_TREE_MAX_DEPTH", "3")),
        session_dir=session_dir,
        session_file=session_dir / "session.json",
    )


settings = load_settings()
