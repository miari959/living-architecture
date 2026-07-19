import sys
import os
import time
import threading
from pathlib import Path

# --- SETUP PATHS ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
HA_PATH = PROJECT_ROOT / "applications" / "external_homeassistant"
sys.path.append(str(HA_PATH))

# --- IMPORTS ---
from src.tracer import ArchitectureTracer
from src.visualizer import PlantUMLGenerator
from homeassistant import __main__ as ha_main

# --- GLOBAL SETTINGS ---
CAPTURE_DURATION_SECONDS = 10  # Duration of the experiment


def spy_and_save(tracer_instance):
    """
    Background thread that waits for the duration, then politely asks the
    Tracer to stop and generate its report BEFORE we kill the process.
    """
    print(f">> [SPY] Monitoring started. Will analyze for {CAPTURE_DURATION_SECONDS} seconds...")

    # 1. Wait for the experiment duration
    time.sleep(CAPTURE_DURATION_SECONDS)

    print("\n" + "!" * 60)
    print(">> [SPY] TIME UP! GENERATING INTELLIGENCE REPORT...")
    print("!" * 60)

    # 2. Define Paths
    json_path = PROJECT_ROOT / "output" / "e4_homeassistant.json"
    puml_path = PROJECT_ROOT / "output" / "e4_homeassistant.puml"

    # 3. CALL THE OFFICIAL STOP METHOD (This triggers the Report + Save)
    try:
        # This single line replaces all the manual saving we did before.
        # It ensures the 'Tracer Intelligence Report' is printed to console.
        tracer_instance.stop_trace(str(json_path))

        # 4. Generate the Diagram
        if json_path.exists():
            print(f">> [SPY] Generating PlantUML Diagram...")
            viz = PlantUMLGenerator(str(json_path))
            viz.generate(str(puml_path))
            print(f">> [SUCCESS] Diagram saved at: {puml_path}")
        else:
            print("!! [ERROR] JSON file missing.")

    except Exception as e:
        print(f"!! [CRITICAL] Report generation failed: {e}")

    # 5. Terminate
    print(">> [SPY] Mission Complete. Terminating Process...")
    os._exit(0)


def main():
    print("--- [EXPERIMENT] Tracing Home Assistant Core ---")

    # 1. Initialize Tracer
    tracer = ArchitectureTracer()
    tracer.start_trace()

    # 2. Start the Spy Thread
    spy_thread = threading.Thread(target=spy_and_save, args=(tracer,), daemon=True)
    spy_thread.start()

    try:
        print(">> [STATUS] Launching Home Assistant...")
        print(f">> [INSTRUCTION] Sit back. The report will appear in {CAPTURE_DURATION_SECONDS}s.")

        # 3. Run HA
        sys.exit(ha_main.main())

    except Exception as e:
        print(f">> [MAIN CRASH] {e}")


if __name__ == "__main__":
    main()