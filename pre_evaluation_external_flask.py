import sys
import os
import traceback
import ast

# =============================================================================
# 1. PATH SETUP
# Must happen before ANY app imports so all src.* and app modules resolve.
# =============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


# =============================================================================
# 2. LEGACY COMPATIBILITY LAYER
# Must be activated BEFORE importing the Flask app or src modules,
# since some patches (ast.Str, SQLAlchemy) must exist at import time.
# =============================================================================
class LegacyCompatibilityLayer:
    """
    Adapts the modern Python / SQLAlchemy 2.0 / Jinja2 3.1 environment
    to support the legacy RealWorld Flask app (Conduit) without modifying
    its source code.
    """

    @staticmethod
    def apply():
        print("[System] Activating Legacy Compatibility Layer...")
        LegacyCompatibilityLayer._patch_ast()
        LegacyCompatibilityLayer._patch_jinja2()
        LegacyCompatibilityLayer._patch_sqlalchemy()
        print("[System] Compatibility Layer Active. Environment Ready.")

    @staticmethod
    def _patch_ast():
        """Polyfill for ast.Str, removed in Python 3.14."""
        if not hasattr(ast, 'Str'):
            class LegacyStr(ast.Constant):
                def __init__(self, s=None, *args, **kwargs):
                    super().__init__(value=s, kind=None)

                @property
                def s(self): return self.value

                @s.setter
                def s(self, val): self.value = val

            ast.Str = LegacyStr

    @staticmethod
    def _patch_jinja2():
        """
        Restores removed Jinja2 features.
        Modern Jinja2 (3.1+) removed specific extensions because they are now built-in.
        Legacy apps still try to import them, causing crashes.
        """
        try:
            import jinja2
            import jinja2.ext
            from markupsafe import escape, Markup

            jinja2.escape = escape
            jinja2.Markup = Markup

            class DummyExtension(jinja2.ext.Extension):
                def __init__(self, environment):
                    super().__init__(environment)

            if not hasattr(jinja2.ext, 'autoescape'):
                jinja2.ext.autoescape = DummyExtension
            if not hasattr(jinja2.ext, 'with_'):
                jinja2.ext.with_ = DummyExtension
            if not hasattr(jinja2.ext, 'do'):
                jinja2.ext.do = DummyExtension

        except ImportError:
            pass

    @staticmethod
    def _patch_sqlalchemy():
        """
        Re-injects deleted SQLAlchemy 2.0 features so the legacy
        Flask-SQLAlchemy wrapper works without crashing.
        """
        try:
            import sqlalchemy
            import sqlalchemy.orm

            if not hasattr(sqlalchemy.orm, 'relation'):
                sqlalchemy.orm.relation = sqlalchemy.orm.relationship
            if not hasattr(sqlalchemy.orm, 'dynamic_loader'):
                sqlalchemy.orm.dynamic_loader = sqlalchemy.orm.relationship

            context_triggers = {
                'engine', 'metadata', 'session', 'query',
                'create_engine', 'MetaData', 'Session',
                'scoped_session', 'mapper'
            }

            def safe_dir(module):
                return [
                    n for n in dir(module)
                    if not n.startswith("_") and n not in context_triggers
                ]

            if not hasattr(sqlalchemy, "__all__"):
                sqlalchemy.__all__ = safe_dir(sqlalchemy)
            if not hasattr(sqlalchemy.orm, "__all__"):
                sqlalchemy.orm.__all__ = safe_dir(sqlalchemy.orm)

        except ImportError:
            pass


# Activate BEFORE any further imports
LegacyCompatibilityLayer.apply()


# =============================================================================
# 3. SRC IMPORTS
# =============================================================================
from src.tracer import ArchitectureTracer, log_tool
from src.filter import ArchitectureFilter
from src.visualizer import PlantUMLGenerator


# =============================================================================
# 4. FLASK APP SETUP
# =============================================================================
def setup_flask_env():
    """
    Add the external Flask app directory to sys.path and import the app factory.
    Uses __file__ (not os.getcwd()) to ensure the path is always correct
    regardless of which directory the script is launched from.
    """
    flask_dir = os.path.join(current_dir, 'applications', 'external_flask')

    log_tool(f"Target directory: {flask_dir}")

    if not os.path.exists(flask_dir):
        print(f"[CRITICAL] Could not find directory: {flask_dir}")
        sys.exit(1)

    if flask_dir not in sys.path:
        sys.path.insert(0, flask_dir)

    try:
        from conduit.app import create_app
        from conduit.settings import TestConfig
        from conduit.extensions import db

        log_tool("Successfully imported Flask app factory.")
        return create_app, TestConfig, db

    except ImportError as e:
        print(f"\n[CRITICAL] Could not import Flask app. Details: {e}")
        traceback.print_exc()
        sys.exit(1)


# Load factory once at module level
create_app, TestConfig, db = setup_flask_env()


# =============================================================================
# 5. EVALUATION RUNNER
# =============================================================================
def run_evaluation():
    """
    Runs the external Flask RealWorld app through the evaluation configurations.
    For each configuration, it generates a JSON trace and a PlantUML diagram.

    A fresh Flask app context and in-memory SQLite DB are created per config
    to ensure each run starts from a clean state.
    """

    # Evaluation configurations — standardized naming across all eval scripts
    configs = [
        {"id": "0", "name": "Stage0_Before_Filtering", "s1": False, "s2": False, "s3": False, "s4": False},
        {"id": "1", "name": "Stage1",                  "s1": True,  "s2": False, "s3": False, "s4": False},
        {"id": "2", "name": "Stage2",                  "s1": True,  "s2": True,  "s3": False, "s4": False},
        {"id": "3", "name": "Stage3",                  "s1": True,  "s2": True,  "s3": True,  "s4": False},
        {"id": "4", "name": "Stage4",                  "s1": True,  "s2": True,  "s3": True,  "s4": True},
    ]

    print(f"[{'=' * 20} STARTING EVALUATION: EXTERNAL FLASK {'=' * 20}]")

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

        # 3. Create a fresh Flask app + in-memory DB per config run
        app = create_app(TestConfig)

        with app.app_context():
            # Create in-memory DB schema for this run
            db.create_all()

            client = app.test_client()

            # 4. Start Tracing
            tracer.start_trace()

            # 5. Simulate User Flow
            # POST /api/users  → exercises registration stack (Controller → Service → DB)
            # GET  /api/articles → exercises read stack (Controller → Repository → DB)
            try:
                import random
                rand_id = random.randint(1000, 9999)

                log_tool(">>> Sending POST /api/users ...")
                response = client.post('/api/users', json={
                    "user": {
                        "username": f"thesis_{rand_id}",
                        "email": f"test_{rand_id}@example.com",
                        "password": "password123"
                    }
                })
                log_tool(f"<<< Response: {response.status_code}")

                log_tool(">>> Sending GET /api/articles ...")
                response = client.get('/api/articles')
                log_tool(f"<<< Response: {response.status_code}")

            except Exception as e:
                print(f"  [Error] Request failed: {e}")

            # 6. Stop Tracing and Save JSON (Stage 2 runs inside tracer.stop_trace)
            json_path = f"output/external_flask_{c['name']}.json"
            tracer.stop_trace(json_path)

            # 7. Generate PlantUML Diagram
            puml_path = f"output/external_flask_{c['name']}.puml"
            print(f"[Visualizer] Generating diagram: {puml_path}")

            try:
                # Pass the same filter configuration into the visualizer so Stage 1b
                # and Stage 3 use the same thresholds and toggles.
                viz = PlantUMLGenerator(json_path)
                viz.filter_engine = current_filter
                viz.generate(puml_path)
            except Exception as e:
                print(f"  [Visualizer Error] Could not generate diagram: {e}")


if __name__ == "__main__":
    run_evaluation()
