"""Token estimation for /stats.

The gateway reports authoritative usage numbers from OpenRouter for each
turn actually sent. This module only estimates tokens for local-only
figures (e.g. total context assembled so far) using tiktoken, and every
value it produces is explicitly labeled as an estimate by the caller.
"""
from __future__ import annotations

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_ENCODING.encode(text))
