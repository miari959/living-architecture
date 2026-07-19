import os
import sys
import django
from django.test import Client
import traceback


# =============================================================================
# DJANGO SETUP
# =============================================================================
def configure_django_environment():
    """Find and configure Django project settings."""

    base_dir = os.path.join(os.getcwd(), 'applications', 'external_django')
    print(f"[Setup] Looking in: {base_dir}")

    # Walk through directories to find settings.py
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
        print("[ERROR] Can't find settings.py!")
        sys.exit(1)

    print(f"[Setup] Found: {settings_path}")
    print(f"[Setup] Project root: {project_root}")

    # Add project to Python path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Set Django settings module
    module_name = f"{package_name}.settings"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", module_name)

    # Initialize Django
    try:
        django.setup()
        print("[Setup] Django ready!\n")
    except Exception:
        print("[ERROR] Django setup failed")
        traceback.print_exc()
        sys.exit(1)


# Run setup first
configure_django_environment()

# Import our tools
from src.tracer import ArchitectureTracer
from src.visualizer import PlantUMLGenerator
from src.filter import ArchitectureFilter


# =============================================================================
# TRACE LIMITER (do not modify tracer.py; cap from the outside)
# =============================================================================
def install_trace_cap(tracer: ArchitectureTracer, max_events: int = 500):
    """
    Stop tracing after max_events *analyzed* events for ALL stages.
    Analyzed = kept + filtered events.
    """
    original_cb = tracer._trace_callback

    def capped_cb(frame, event, arg):
        # Check cap BEFORE processing
        analyzed = len(tracer.trace_log) + tracer.total_filtered_count
        if analyzed >= max_events:
            sys.settrace(None)   # disables tracing globally
            return None          # stop tracing in this scope

        # Process the event normally
        result = original_cb(frame, event, arg)
        return result

    tracer._trace_callback = capped_cb


# =============================================================================
# RUN EVALUATION
# =============================================================================
def run_evaluation():
    """Test Django app with different filter stages (all capped at 500)."""

    MAX_EVENTS = 500

    print("=" * 80)
    print("DJANGO EVALUATION - Testing 4-Stage Filtering (10 Scenarios)")
    print("=" * 80)
    print(f"[Config] All stages capped at: {MAX_EVENTS} events")

    # Test configurations
    configs = [
        {"id": "0", "name": "Stage0_Before_Filtering", "s1": False, "s2": False, "s3": False, "s4": False},
        {"id": "1", "name": "Stage1", "s1": True, "s2": False, "s3": False, "s4": False},
        {"id": "2", "name": "Stage2", "s1": True, "s2": True, "s3": False, "s4": False},
        {"id": "3", "name": "Stage3", "s1": True, "s2": True, "s3": True, "s4": False},
        {"id": "4", "name": "Stage4", "s1": True, "s2": True, "s3": True, "s4": True},
    ]

    # Run each configuration
    for config in configs:
        print(f"\n>>> Testing: {config['name']}")

        # Setup filter
        my_filter = ArchitectureFilter(
            stage1=config['s1'],
            stage2=config['s2'],
            stage3=config['s3'],
            stage4=config['s4']
        )

        # Setup tracer + client
        tracer = ArchitectureTracer(custom_filter=my_filter)
        client = Client()

        # Warm up Django stack without tracing
        try:
            client.get("/api/tags/")
        except Exception as e:
            print(f"   [Warmup warning] {e}")

        # Install cap for ALL stages
        install_trace_cap(tracer, MAX_EVENTS)

        # Start recording
        tracer.start_trace()

        # Execute 10 different scenarios
        try:
            # Scenario 1: List all tags
            print(f"   Scenario 1: GET /api/tags/")
            client.get("/api/tags/")

            # Scenario 2: Browse articles with limit
            print(f"   Scenario 2: GET /api/articles/?limit=1")
            client.get("/api/articles/", data={"limit": 1})

            # Scenario 3: Get article feed
            print(f"   Scenario 3: GET /api/articles/feed/")
            client.get("/api/articles/feed/")

            # Scenario 4: Get user profile
            print(f"   Scenario 4: GET /api/profiles/testuser/")
            client.get("/api/profiles/testuser/")

            # Scenario 5: Search articles by tag
            print(f"   Scenario 5: GET /api/articles/?tag=test")
            client.get("/api/articles/", data={"tag": "test", "limit": 2})

            # Scenario 6: Search articles by author
            print(f"   Scenario 6: GET /api/articles/?author=test")
            client.get("/api/articles/", data={"author": "test", "limit": 2})

            # Scenario 7: Search favorited articles
            print(f"   Scenario 7: GET /api/articles/?favorited=user")
            client.get("/api/articles/", data={"favorited": "user", "limit": 2})

            # Scenario 8: Get single article by slug
            print(f"   Scenario 8: GET /api/articles/test-slug/")
            client.get("/api/articles/test-slug/")

            # Scenario 9: Browse articles with offset (pagination)
            print(f"   Scenario 9: GET /api/articles/?offset=5&limit=2")
            client.get("/api/articles/", data={"offset": 5, "limit": 2})

            # Scenario 10: Get multiple tags in one request
            print(f"   Scenario 10: GET /api/tags/ (repeat)")
            client.get("/api/tags/")

        except Exception as e:
            print(f"   Warning: {e}")

        # Save trace
        json_file = f"output/django_{config['name']}.json"
        tracer.stop_trace(json_file)

        # Generate diagram
        puml_file = f"output/django_{config['name']}.puml"
        print(f"[Visualizer] Generating diagram: {puml_file}")

        viz = PlantUMLGenerator(json_file)
        viz.generate(puml_file)

    print("\n" + "=" * 80)
    print("Evaluation complete!")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
