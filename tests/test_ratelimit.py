"""Tests for the gateway-wide minimum-interval throttle placed in front of
OpenRouter calls, so bursts of quick messages don't trip free-tier rate
limits or burn through a low-balance account's quota."""
import asyncio
import time

import pytest

from gateway.ratelimit import MinIntervalThrottle


@pytest.mark.asyncio
async def test_first_call_does_not_wait():
    throttle = MinIntervalThrottle(min_interval_seconds=1.0)
    start = time.monotonic()
    await throttle.wait()
    assert time.monotonic() - start < 0.2


@pytest.mark.asyncio
async def test_second_call_waits_out_remaining_interval():
    throttle = MinIntervalThrottle(min_interval_seconds=0.3)
    await throttle.wait()
    start = time.monotonic()
    await throttle.wait()
    assert time.monotonic() - start >= 0.25


@pytest.mark.asyncio
async def test_zero_interval_never_waits():
    throttle = MinIntervalThrottle(min_interval_seconds=0)
    await throttle.wait()
    start = time.monotonic()
    await throttle.wait()
    assert time.monotonic() - start < 0.1


@pytest.mark.asyncio
async def test_concurrent_calls_are_serialized_with_spacing():
    throttle = MinIntervalThrottle(min_interval_seconds=0.2)
    start = time.monotonic()
    await asyncio.gather(*(throttle.wait() for _ in range(3)))
    elapsed = time.monotonic() - start
    assert elapsed >= 0.35
