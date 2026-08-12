"""A minimum-interval throttle placed in front of every OpenRouter call.

Free-tier OpenRouter models enforce their own per-account rate limits, and
a low/zero credit balance gets the strictest ones. Sending messages back
to back can burn through that quota in seconds and starts returning 429s.
Serializing every gateway->OpenRouter call through this throttle - so
consecutive requests are always spaced at least `min_interval_seconds`
apart - keeps Chemisto comfortably under those limits without requiring
the user to pace themselves.
"""
from __future__ import annotations

import asyncio
import time


class MinIntervalThrottle:
    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call_at: float | None = None

    async def wait(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            if self._last_call_at is not None:
                remaining = self._min_interval - (now - self._last_call_at)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_call_at = time.monotonic()
