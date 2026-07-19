import sys
import os

# 1. PATH SETUP
# Ensure the project root is in sys.path so we can import 'src' modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Add the FastAPI app directory to path so internal imports (app.*) resolve correctly
experiment_path = os.path.join(current_dir, 'applications', 'external_fastapi')
if experiment_path not in sys.path:
    sys.path.insert(0, experiment_path)

from src.tracer import ArchitectureTracer, log_tool
from src.filter import ArchitectureFilter
from src.visualizer import PlantUMLGenerator


def setup_environment():
    """
    Configure environment variables required by the FastAPI RealWorld app.
    These are set before the app is imported so get_app_settings() picks them up.
    """
    os.environ.setdefault("SECRET_KEY", "evaluation-secret-key-not-for-production")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./evaluation_test.db")
    os.environ.setdefault("ALLOWED_HOSTS", '["*"]')
    os.environ.setdefault("PROJECT_NAME", "FastAPI RealWorld Evaluation")
    os.environ.setdefault("API_PREFIX", "/api")
    log_tool("Environment variables configured.")


def load_app():
    """
    Import and return the FastAPI application instance from the real external app.
    The app is loaded once before the evaluation loop — we only trace the
    request handling, not the app startup/configuration overhead.
    """
    log_tool("Importing FastAPI app from main.py...")
    try:
        from main import app
        log_tool("SUCCESS: FastAPI app loaded.")
        return app
    except Exception as e:
        log_tool(f"[Fatal] Failed to load app: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_evaluation():
    """
    Runs the external FastAPI RealWorld app through the evaluation configurations.
    For each configuration, it generates a JSON trace and a PlantUML diagram.

    Uses FastAPI's built-in TestClient (wraps httpx) to fire real HTTP requests
    against the app in-process — no running server needed.
    """

    # Evaluation configurations
    configs = [
        {"id": "0", "name": "Stage0_Before_Filtering", "s1": False, "s2": False, "s3": False, "s4": False},
        {"id": "1", "name": "Stage1",                  "s1": True,  "s2": False, "s3": False, "s4": False},
        {"id": "2", "name": "Stage2",                  "s1": True,  "s2": True,  "s3": False, "s4": False},
        {"id": "3", "name": "Stage3",                  "s1": True,  "s2": True,  "s3": True,  "s4": False},
        {"id": "4", "name": "Stage4",                  "s1": True,  "s2": True,  "s3": True,  "s4": True},
    ]

    # Setup environment and load the real app ONCE before the loop
    setup_environment()
    app = load_app()
    if app is None:
        print("[CRITICAL] Could not load FastAPI app. Aborting evaluation.")
        return

    # Import TestClient after the app path is set up
    from fastapi.testclient import TestClient

    print(f"[{'=' * 20} STARTING EVALUATION: EXTERNAL FASTAPI {'=' * 20}]")

    for c in configs:
        print(f"\n>>> TESTING CONFIG {c['id']}: {c['name']}")

        # 1. Configure the Filter (controls Stage 1–4 behaviour globally)
        current_filter = ArchitectureFilter(
            stage1=c["s1"],
            stage2=c["s2"],
            stage3=c["s3"],
            stage4=c["s4"],
        )

        # 2. Initialize Tracer with the Custom Filter
        tracer = ArchitectureTracer(custom_filter=current_filter)

        # 3. Create a fresh TestClient per config run
        # raise_server_exceptions=False prevents crashes from propagating
        # to the evaluation loop if the app returns 500 internally.
        client = TestClient(app, raise_server_exceptions=False)

        # 4. Start Tracing
        tracer.start_trace()

        # 5. Execute HTTP Scenario
        # GET /api/articles exercises the full stack:
        # Router → Controller → Service → Repository → DB
        try:
            log_tool(">>> Sending GET /api/articles ...")
            response = client.get("/api/articles")
            log_tool(f"<<< Response: {response.status_code}")
        except Exception as e:
            print(f"  [Error] Request failed: {e}")

        # 6. Stop Tracing and Save JSON (Stage 2 runs inside tracer.stop_trace)
        json_path = f"output/external_fastapi_{c['name']}.json"
        tracer.stop_trace(json_path)

        # 7. Generate PlantUML Diagram
        puml_path = f"output/external_fastapi_{c['name']}.puml"
        print(f"[Visualizer] Generating diagram: {puml_path}")

        try:
            viz = PlantUMLGenerator(json_path)
            viz.filter_engine = current_filter
            viz.generate(puml_path)
        except Exception as e:
            print(f"  [Visualizer Error] Could not generate diagram: {e}")


if __name__ == "__main__":
    run_evaluation()
