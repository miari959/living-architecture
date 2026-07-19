"""
Process-wide serialization for trace execution.

sys.settrace() is global interpreter state and several runners also mutate global
state (threading.settrace, django.setup, module singletons), so only ONE trace may
run at a time in the process. This module provides the single lock every trace
request must hold, plus a small tracker so the API can report queue depth.

HARD DEPLOYMENT CONSTRAINT: run uvicorn with --workers 1. Multiple worker
processes would each have their own lock and defeat the serialization.
"""
import asyncio

# One lock for the whole process. Created lazily on the running event loop.
_TRACE_LOCK: asyncio.Lock | None = None

# Number of requests currently waiting for or holding the lock.
_waiting = 0


def get_lock() -> asyncio.Lock:
    global _TRACE_LOCK
    if _TRACE_LOCK is None:
        _TRACE_LOCK = asyncio.Lock()
    return _TRACE_LOCK


def queue_depth() -> int:
    """How many trace requests are in flight (waiting + running)."""
    return _waiting


def _inc() -> None:
    global _waiting
    _waiting += 1


def _dec() -> None:
    global _waiting
    _waiting = max(0, _waiting - 1)
