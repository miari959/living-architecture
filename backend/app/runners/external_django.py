"""
Runner for the external Django RealWorld app (Conduit).

Mirrors pre_evaluation_external_django.py with two corrections for a long-lived
server process (vs. the original one-shot CLI script):
  1. The original located applications/external_django via os.getcwd(); that
     breaks when the server's working directory isn't the project root. Here we
     resolve it from PROJECT_ROOT (i.e. __file__-relative), like the other 7 runners.
  2. django.setup() must run exactly once per process, so it's guarded here at
     module import time rather than per request.

The 10 scenarios are all read-only GETs against the vendored db.sqlite3, so no
per-run DB reset is needed (no writes -> no cross-request pollution or growth).

install_trace_cap() is reused verbatim from the original: Django's request stack
is very deep/chatty, so tracing is capped at 500 analyzed events.
"""
import os
import sys

from .base import PROJECT_ROOT, RunOutcome, new_tracer, run_with_tracer
from src.filter import ArchitectureFilter
from src.tracer import ArchitectureTracer


# =============================================================================
# One-time Django configuration (runs once at module import)
# =============================================================================
def _configure_django_once():
    base_dir = os.path.join(str(PROJECT_ROOT), 'applications', 'external_django')

    settings_path = None
    package_name = None
    project_root = None
    for root, dirs, files in os.walk(base_dir):
        if 'settings.py' in files:
            settings_path = os.path.join(root, 'settings.py')
            package_name = os.path.basename(root)
            project_root = os.path.dirname(root)
            break

    if not settings_path:
        raise RuntimeError(f"Could not find Django settings.py under {base_dir}")

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{package_name}.settings")

    import django
    django.setup()


_configure_django_once()

from django.test import Client  # noqa: E402


# =============================================================================
# Trace cap (reused verbatim from pre_evaluation_external_django.py)
# =============================================================================
def install_trace_cap(tracer: ArchitectureTracer, max_events: int = 500):
    """Stop tracing after max_events *analyzed* (kept + filtered) events."""
    original_cb = tracer._trace_callback

    def capped_cb(frame, event, arg):
        analyzed = len(tracer.trace_log) + tracer.total_filtered_count
        if analyzed >= max_events:
            sys.settrace(None)
            return None
        return original_cb(frame, event, arg)

    tracer._trace_callback = capped_cb


_SCENARIOS = [
    ("/api/tags/", None),
    ("/api/articles/", {"limit": 1}),
    ("/api/articles/feed/", None),
    ("/api/profiles/testuser/", None),
    ("/api/articles/", {"tag": "test", "limit": 2}),
    ("/api/articles/", {"author": "test", "limit": 2}),
    ("/api/articles/", {"favorited": "user", "limit": 2}),
    ("/api/articles/test-slug/", None),
    ("/api/articles/", {"offset": 5, "limit": 2}),
    ("/api/tags/", None),
]

MAX_EVENTS = 500


class ExternalDjangoRunner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        tracer = new_tracer(filter_engine)
        warnings = []

        client = Client()

        # Warm up the Django stack WITHOUT tracing (first request lazily imports
        # a lot of machinery we don't want in the diagram).
        try:
            client.get("/api/tags/")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"warmup: {type(e).__name__}: {e}")

        # No-self closure so traced app code's outermost caller is External_User.
        def action():
            for path, data in _SCENARIOS:
                if data:
                    client.get(path, data=data)
                else:
                    client.get(path)

        install_trace_cap(tracer, MAX_EVENTS)
        # Delegate the traced portion to a module-level helper so this runner's
        # frame is never the direct caller of a traced call (no stray participant).
        run_with_tracer(tracer, action, warnings)

        return RunOutcome(tracer=tracer, warnings=warnings)
