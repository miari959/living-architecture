"""
Shared plumbing for the 8 app runners.

Each runner refactors the setup + execution logic of one pre_evaluation_*.py
script into a reusable object exposing `run(filter_engine) -> RunOutcome`. The
FastAPI layer calls every runner uniformly through this interface.

One-time, process-wide setup (monkeypatches, env vars, app-factory imports,
django.setup()) lives at module import time in each runner. Only the per-request
work (exercising the target app under a fresh tracer) happens inside run().
"""
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Protocol

# <root>/backend/app/runners/base.py -> parents[3] == project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tracer import ArchitectureTracer  # noqa: E402
from src.filter import ArchitectureFilter  # noqa: E402


@dataclass
class RunOutcome:
    """Result of one trace run: the finished tracer plus any non-fatal warnings."""
    tracer: ArchitectureTracer
    warnings: List[str] = field(default_factory=list)


class AppRunner(Protocol):
    """A runner exercises one target app under a tracer for one request."""

    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        ...


def new_tracer(filter_engine: ArchitectureFilter) -> ArchitectureTracer:
    return ArchitectureTracer(custom_filter=filter_engine)


def finalize(tracer: ArchitectureTracer) -> None:
    """
    Run stop_trace() (which applies Stage 2 + Stage 3 post-processing and leaves
    the final filtered events in tracer.trace_log) while directing its mandatory
    JSON side-effect write to a throwaway temp file we immediately delete. The
    web path never needs the on-disk JSON; it reads tracer.trace_log directly.
    """
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        tracer.stop_trace(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_simple(filter_engine: ArchitectureFilter, action: Callable[[], None]) -> RunOutcome:
    """
    The common single-threaded, synchronous path: start trace -> run action ->
    finalize. Catches (and reports as a warning) any exception the target app
    raises, matching the resilience of the original pre_evaluation_*.py scripts
    so one app's crash never 500s the whole endpoint.

    IMPORTANT: `action` must be a module-level function or a closure that does
    NOT reference `self`. The tracer records a callee's caller as
    caller_frame.f_locals['self'].__class__.__name__ when 'self' is present, so
    invoking a target from a bound runner method (which has `self`) would make
    the runner class appear as a participant. Calling via a no-self closure keeps
    the caller as "External_User", exactly like the original pre_evaluation_*.py
    scripts (which drove the apps from module-level functions). This is purely a
    property of how we CALL the apps — it changes nothing in the tracer.
    """
    tracer = new_tracer(filter_engine)
    warnings: List[str] = []
    tracer.start_trace()
    try:
        action()
    except Exception as e:  # noqa: BLE001 - deliberately broad, mirrors originals
        warnings.append(f"{type(e).__name__}: {e}")
    finally:
        finalize(tracer)
    return RunOutcome(tracer=tracer, warnings=warnings)


def run_with_tracer(tracer: ArchitectureTracer, action: Callable[[], None], warnings: List[str]) -> None:
    """
    Drive an already-configured tracer (e.g. one with a custom event cap or
    inside a mock/patch context) through start -> action -> finalize.

    This is module-level on purpose: because it (not the runner's bound method)
    is the frame that calls start_trace() and then action(), the runner class
    never appears as the direct caller of a traced call, so it doesn't leak into
    the diagram as a stray participant. Runners with a non-standard lifecycle
    (Django's cap, Zulip's requests patch) call this instead of run_simple.
    `action` must not reference `self`.
    """
    tracer.start_trace()
    try:
        action()
    except Exception as e:  # noqa: BLE001
        warnings.append(f"{type(e).__name__}: {e}")
    finally:
        finalize(tracer)


def run_threaded(filter_engine: ArchitectureFilter, action: Callable[[], None]) -> RunOutcome:
    """
    Like run_simple, but also installs the trace callback via threading.settrace
    so calls inside threads the target spawns are captured too. Mirrors the
    threading.settrace(tracer._trace_callback) / threading.settrace(None) dance
    from pre_evaluation_console_app_2.py. `action` must not reference `self`.
    """
    import threading

    tracer = new_tracer(filter_engine)
    warnings: List[str] = []
    tracer.start_trace()
    threading.settrace(tracer._trace_callback)
    try:
        action()
    except Exception as e:  # noqa: BLE001
        warnings.append(f"{type(e).__name__}: {e}")
    finally:
        threading.settrace(None)
        finalize(tracer)
    return RunOutcome(tracer=tracer, warnings=warnings)
