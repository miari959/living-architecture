import sys
import os
from unittest.mock import MagicMock, patch

# =============================================================================
# 1. PATH SETUP
# Must happen before ANY src.* imports.
# =============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# =============================================================================
# 2. IMPORTS
# =============================================================================
try:
    import zulip
    print("[Setup] Successfully imported real 'zulip' package.")
except ImportError:
    print("[CRITICAL] 'zulip' package not found. Run: pip install zulip")
    sys.exit(1)

from src.tracer import ArchitectureTracer, log_tool
from src.filter import ArchitectureFilter
from src.visualizer import PlantUMLGenerator


# =============================================================================
# 3. HELPERS
# =============================================================================
def get_mock_response():
    """
    Build a rich mock HTTP response that satisfies all Zulip client calls.
    Defined as a function so each config run gets a fresh MagicMock instance.
    """
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
        "messages": []
    }
    return mock


def trace_scenario(tracer, current_filter, scenario_id, scenario_name, config_name, action):
    """
    Wraps a single Zulip scenario in a start→action→stop→visualize cycle.
    Returns the result of the action (e.g., the newly created client).
    """
    log_tool(f"--- Running Scenario: {scenario_id}_{scenario_name} [{config_name}] ---")

    tracer.start_trace()
    result = None

    try:
        result = action()
    except Exception as e:
        print(f"  [Error] Scenario {scenario_id} failed: {e}")

    json_path = f"output/external_zulip_{config_name}_{scenario_id}_{scenario_name}.json"
    tracer.stop_trace(json_path)

    puml_path = json_path.replace(".json", ".puml")
    try:
        viz = PlantUMLGenerator(json_path)
        viz.filter_engine = current_filter
        viz.generate(puml_path)
    except Exception as e:
        print(f"  [Visualizer Error] {scenario_id}_{scenario_name}: {e}")

    return result


# =============================================================================
# 4. EVALUATION RUNNER
# =============================================================================
def run_evaluation():
    """
    Runs 10 Zulip client scenarios through all 5 evaluation stage configurations.
    Each scenario is independently traced (start → action → stop → visualize).
    A fresh zulip.Client is created in Scenario 01 (Init) per config run and
    reused for Scenarios 02–10.

    HTTP calls are intercepted via unittest.mock so no real Zulip server is needed.
    """

    # Evaluation configurations — standardized naming across all eval scripts
    configs = [
        {"id": "0", "name": "Stage0_Before_Filtering", "s1": False, "s2": False, "s3": False, "s4": False},
        {"id": "1", "name": "Stage1",                  "s1": True,  "s2": False, "s3": False, "s4": False},
        {"id": "2", "name": "Stage2",                  "s1": True,  "s2": True,  "s3": False, "s4": False},
        {"id": "3", "name": "Stage3",                  "s1": True,  "s2": True,  "s3": True,  "s4": False},
        {"id": "4", "name": "Stage4",                  "s1": True,  "s2": True,  "s3": True,  "s4": True},
    ]

    print(f"[{'=' * 20} STARTING EVALUATION: EXTERNAL ZULIP {'=' * 20}]")

    for c in configs:
        print(f"\n>>> TESTING CONFIG {c['id']}: {c['name']}")

        # 1. Configure the Filter (controls Stage 1–4 behaviour globally)
        current_filter = ArchitectureFilter(
            stage1=c["s1"],
            stage2=c["s2"],
            stage3=c["s3"],
            stage4=c["s4"],
        )

        # 2. Fresh mock response per config run
        mock_r = get_mock_response()

        # Helper: create a fresh tracer per scenario, sharing the same filter
        def make_tracer():
            return ArchitectureTracer(custom_filter=current_filter)

        with patch('requests.Session.request', return_value=mock_r):

            # --- Scenario 01: Client Initialization ---
            client = trace_scenario(
                make_tracer(), current_filter,
                "01", "Init", c["name"],
                lambda: zulip.Client(
                    email="test@zulip.com",
                    api_key="secret",
                    site="https://chat.zulip.org"
                )
            )

            # Guard: if client init failed, skip remaining scenarios for this config
            if client is None:
                print(f"  [Warning] Client init failed for config {c['name']}. Skipping remaining scenarios.")
                continue

            # --- Scenario 02: Send Message (Core Logic) ---
            trace_scenario(
                make_tracer(), current_filter,
                "02", "SendMsg", c["name"],
                lambda: client.send_message({
                    "type": "stream",
                    "to": "general",
                    "subject": "Thesis",
                    "content": "Tracing real code!"
                })
            )

            # --- Scenario 03: Get Profile (Read Logic) ---
            trace_scenario(
                make_tracer(), current_filter,
                "03", "GetProfile", c["name"],
                lambda: client.get_profile()
            )

            # --- Scenario 04: Register Queue (Event Logic) ---
            trace_scenario(
                make_tracer(), current_filter,
                "04", "RegisterQueue", c["name"],
                lambda: client.register(event_types=["message", "heartbeat"])
            )

            # --- Scenario 05: Update Message Flags (State Logic) ---
            trace_scenario(
                make_tracer(), current_filter,
                "05", "UpdateFlags", c["name"],
                lambda: client.update_message_flags({
                    "messages": [42],
                    "op": "add",
                    "flag": "read"
                })
            )

            # --- Scenario 06: Upload File (Data Handling) ---
            mock_file = MagicMock()
            mock_file.name = "thesis_data.txt"
            mock_file.read.return_value = b"simulation data"
            trace_scenario(
                make_tracer(), current_filter,
                "06", "Upload", c["name"],
                lambda: client.upload_file(mock_file)
            )

            # --- Scenario 07: Subscribe to Stream (Stream Management) ---
            trace_scenario(
                make_tracer(), current_filter,
                "07", "Subscribe", c["name"],
                lambda: client.add_subscriptions(streams=[{"name": "engineering"}])
            )

            # --- Scenario 08: Render Message (Processing Logic) ---
            trace_scenario(
                make_tracer(), current_filter,
                "08", "RenderMsg", c["name"],
                lambda: client.render_message({
                    "content": "Analysis of **architectural** signals."
                })
            )

            # --- Scenario 09: Typing Status (Real-time Event) ---
            trace_scenario(
                make_tracer(), current_filter,
                "09", "Typing", c["name"],
                lambda: client.set_typing_status({"to": [101], "op": "start"})
            )

            # --- Scenario 10: Get Message History (DB Retrieval) ---
            trace_scenario(
                make_tracer(), current_filter,
                "10", "GetHistory", c["name"],
                lambda: client.get_messages({
                    "anchor": "newest",
                    "num_before": 10,
                    "num_after": 0,
                    "narrow": [{"operator": "sender", "operand": "alice@zulip.com"}]
                })
            )

        print(f"  [Done] Config {c['name']} complete — 10 scenarios traced.")


if __name__ == "__main__":
    run_evaluation()
