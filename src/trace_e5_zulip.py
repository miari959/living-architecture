import sys
import os
from pathlib import Path

# --- SETUP PATHS ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
ZULIP_PATH = PROJECT_ROOT / "applications" / "external_zulip"
sys.path.append(str(ZULIP_PATH))

# --- CONFIGURATION ---
# We force Zulip to use its settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")

# --- IMPORTS ---
from src.tracer import ArchitectureTracer
from src.visualizer import PlantUMLGenerator


def main():
    print("--- [EXPERIMENT] Tracing Zulip (Architecture Analysis) ---")

    # 1. Initialize Tracer
    tracer = ArchitectureTracer()

    # 2. Define Output Paths
    json_path = PROJECT_ROOT / "output" / "e5_zulip.json"
    puml_path = PROJECT_ROOT / "output" / "e5_zulip.puml"

    try:
        print("[TRACER] Starting Analysis...")
        tracer.start_trace()

        # --- TARGET EXECUTION START ---
        import django
        from django.conf import settings

        print("[TARGET] Booting Django/Zulip Core...")

        # This attempts to load the entire application architecture.
        # If it fails (due to missing DB), the 'finally' block ensures we still get a report.
        django.setup()

        print("[TARGET] Scanning URL Configurations...")
        from django.urls import get_resolver
        resolver = get_resolver()
        print(f"[TARGET] Success! Mapped {len(resolver.url_patterns)} architectural entry points.")
        # --- TARGET EXECUTION END ---

    except ImportError as e:
        print(f"\n[CRITICAL ERROR] Missing Dependency: {e}")
        print(">> Solution: pip install -r applications/external_zulip/requirements.txt")

    except Exception as e:
        # Zulip WILL likely throw an error here because Postgres is not running.
        # We catch it so the script doesn't crash, allowing the report to generate.
        print(f"\n[TARGET STOPPED] Application halted: {e}")
        print(">> Note: This is expected if the Database is not running.")
        print(">> The Tracer has captured the initialization logic up to this point.")

    finally:
        # 3. Stop Tracer & Generate Report
        # This guarantees the "Tracer Intelligence Report" table is printed
        print("\n" + "=" * 60)
        print("[TRACER] Finalizing Analysis...")
        tracer.stop_trace(str(json_path))
        print("=" * 60)

        # 4. Generate Diagram
        if json_path.exists():
            print(f"[VISUALIZER] Generating PlantUML Diagram...")
            viz = PlantUMLGenerator(str(json_path))
            viz.generate(str(puml_path))
            print(f"[SUCCESS] Architecture Map saved to: {puml_path}")
        else:
            print("[ERROR] No trace data was saved.")


if __name__ == "__main__":
    main()