"""
The trace-execution service: the single entry point the API calls to run a trace.

Serializes all runs behind the process-wide lock, executes the (blocking,
sys.settrace-based) runner in a worker thread so the event loop stays responsive,
then builds the Mermaid diagram and structured stats for the response.
"""
import time

import anyio

from src.filter import ArchitectureFilter
from src.mermaid_visualizer import MermaidGenerator

from ..runners.base import RunOutcome
from ..runners.registry import get_runner
from . import trace_lock


def _report_dict(outcome: RunOutcome) -> dict:
    """
    Structured filtering stats. Uses the tracer's additive get_report_dict()
    if present, else computes the same numbers from public attributes (keeps
    the backend working even against an untouched tracer).
    """
    tracer = outcome.tracer
    if hasattr(tracer, "get_report_dict"):
        return tracer.get_report_dict()

    kept = len(tracer.trace_log)
    removed = tracer.total_filtered_count + tracer.stage2_removed + tracer.stage3_removed
    total = kept + removed
    return {
        "total_events": total,
        "kept": kept,
        "removed": removed,
        "reduction_pct": round((removed / total * 100) if total else 0.0, 2),
        "stage1_removed": tracer.report_stats.get("Stage 1 (Utility/Lib)", 0),
        "stage2_removed": tracer.stage2_removed,
        "stage3_removed": tracer.stage3_removed,
        "layer_breakdown": dict(tracer.layer_stats),
    }


def _run_blocking(app_id: str, stage1: bool, stage2: bool, stage3: bool, stage4: bool) -> dict:
    """The synchronous trace work, executed in a worker thread."""
    meta = get_runner(app_id)
    if meta is None:
        raise KeyError(app_id)

    filter_engine = ArchitectureFilter(stage1=stage1, stage2=stage2, stage3=stage3, stage4=stage4)
    outcome = meta.runner.run(filter_engine)

    mermaid = MermaidGenerator(
        trace_data=list(outcome.tracer.trace_log),
        filter_engine=filter_engine,
    ).generate()

    stats = _report_dict(outcome)
    return {
        "mermaid": mermaid,
        "stats": stats,
        "warnings": outcome.warnings,
        "empty": mermaid.count("->>") == 0,
    }


async def run_trace(app_id: str, stage1: bool, stage2: bool, stage3: bool, stage4: bool) -> dict:
    """
    Public async entry point. Acquires the process-wide trace lock, runs the
    blocking trace off the event loop, and returns a result dict for the API.
    """
    trace_lock._inc()
    started = time.perf_counter()
    try:
        async with trace_lock.get_lock():
            result = await anyio.to_thread.run_sync(
                _run_blocking, app_id, stage1, stage2, stage3, stage4
            )
    finally:
        trace_lock._dec()

    result["app_id"] = app_id
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result
