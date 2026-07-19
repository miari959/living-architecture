"""
Runner for the Zulip API client (the `zulip` PyPI package).

Mirrors pre_evaluation_external_zulip.py's target logic, but CONSOLIDATED into a
single continuous trace spanning all 10 scenarios (the original produced 10
separate diagrams). This matches the single-trace-multi-scenario shape of the
Home Assistant runner, for UX parity across all 8 apps.

Despite the vendored applications/external_zulip/ Django server folder existing,
this runner never touches it — it only imports the small `zulip` client library
and mocks all HTTP via unittest.mock, so no Zulip server / Postgres / network is
needed.
"""
from unittest.mock import MagicMock, patch

from .base import PROJECT_ROOT, RunOutcome, new_tracer, run_with_tracer  # noqa: F401
from src.filter import ArchitectureFilter

import zulip

# One-time warmup: the first zulip.Client(...) / API call triggers a cascade of
# lazy imports (importlib machinery: ModuleSpec, FileFinder, _ModuleLock, ...).
# We do a throwaway client + call at import time, OUTSIDE any trace, so that
# import noise is already resolved and doesn't pollute the diagram on real runs.
def _warmup():
    try:
        with patch('requests.Session.request', return_value=_mock_response()):
            c = zulip.Client(email="warm@up.com", api_key="x", site="https://example.com")
            c.get_profile()
    except Exception:
        pass


def _mock_response():
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "result": "success",
        "msg": "",
        "id": 42,
        "zulip_version": "8.0",
        "queue_id": "12345",
        "last_event_id": -1,
        "uri": "https://chat.zulip.org",
        "rendered": "<p><b>Heavy</b> processing</p>",
        "subscriptions": [],
        "messages": [],
    }
    return mock


class ExternalZulipRunner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        tracer = new_tracer(filter_engine)
        warnings = []

        mock_file = MagicMock()
        mock_file.name = "thesis_data.txt"
        mock_file.read.return_value = b"simulation data"

        with patch('requests.Session.request', return_value=_mock_response()):
            # No-self closure: creating the client and calling the API from here
            # (rather than from this bound method) keeps the traced caller as
            # External_User instead of ExternalZulipRunner.
            def action():
                client = zulip.Client(
                    email="test@zulip.com",
                    api_key="secret",
                    site="https://chat.zulip.org",
                )
                scenarios = [
                    ("SendMsg", lambda: client.send_message({
                        "type": "stream", "to": "general",
                        "subject": "Thesis", "content": "Tracing real code!",
                    })),
                    ("GetProfile", lambda: client.get_profile()),
                    ("RegisterQueue", lambda: client.register(event_types=["message", "heartbeat"])),
                    ("UpdateFlags", lambda: client.update_message_flags({
                        "messages": [42], "op": "add", "flag": "read",
                    })),
                    ("Upload", lambda: client.upload_file(mock_file)),
                    ("Subscribe", lambda: client.add_subscriptions(streams=[{"name": "engineering"}])),
                    ("RenderMsg", lambda: client.render_message({
                        "content": "Analysis of **architectural** signals.",
                    })),
                    ("Typing", lambda: client.set_typing_status({"to": [101], "op": "start"})),
                    ("GetHistory", lambda: client.get_messages({
                        "anchor": "newest", "num_before": 10, "num_after": 0,
                        "narrow": [{"operator": "sender", "operand": "alice@zulip.com"}],
                    })),
                ]
                for name, act in scenarios:
                    try:
                        act()
                    except Exception as e:  # noqa: BLE001
                        warnings.append(f"{name}: {type(e).__name__}: {e}")

            # Module-level helper drives the trace so this runner doesn't leak
            # as a participant (see run_with_tracer docstring).
            run_with_tracer(tracer, action, warnings)

        return RunOutcome(tracer=tracer, warnings=warnings)


# Resolve zulip's lazy imports once, outside any trace, so the import machinery
# doesn't pollute the diagram on the first real run.
_warmup()
