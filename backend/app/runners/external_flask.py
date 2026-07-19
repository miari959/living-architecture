"""
Runner for the external Flask RealWorld app (Conduit).

Mirrors pre_evaluation_external_flask.py:
  - The LegacyCompatibilityLayer (ast.Str / Jinja2 / SQLAlchemy shims) MUST be
    applied before the Flask app or SQLAlchemy are imported. Done once here at
    module import time.
  - A fresh Flask app + fresh in-memory SQLite DB are created per run so each
    request starts from clean state, then a test client exercises the stack:
    POST /api/users (register) and GET /api/articles (read).
"""
import ast
import os
import sys

from .base import PROJECT_ROOT, RunOutcome, run_simple
from src.filter import ArchitectureFilter


# =============================================================================
# Legacy compatibility layer (must run BEFORE importing the Flask app / SQLAlchemy)
# Copied from pre_evaluation_external_flask.py; applied exactly once.
# =============================================================================
class _LegacyCompatibilityLayer:
    @staticmethod
    def apply():
        _LegacyCompatibilityLayer._patch_ast()
        _LegacyCompatibilityLayer._patch_jinja2()
        _LegacyCompatibilityLayer._patch_sqlalchemy()

    @staticmethod
    def _patch_ast():
        if not hasattr(ast, 'Str'):
            class LegacyStr(ast.Constant):
                def __init__(self, s=None, *args, **kwargs):
                    super().__init__(value=s, kind=None)

                @property
                def s(self):
                    return self.value

                @s.setter
                def s(self, val):
                    self.value = val

            ast.Str = LegacyStr

    @staticmethod
    def _patch_jinja2():
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


_LegacyCompatibilityLayer.apply()

# --- Now safe to put the Flask app on the path and import its factory (once) ---
_FLASK_DIR = os.path.join(str(PROJECT_ROOT), 'applications', 'external_flask')
if _FLASK_DIR not in sys.path:
    sys.path.insert(0, _FLASK_DIR)

from conduit.app import create_app  # noqa: E402
from conduit.settings import TestConfig  # noqa: E402
from conduit.extensions import db  # noqa: E402


class ExternalFlaskRunner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        import random

        # Fresh app + in-memory DB per run. This setup happens BEFORE tracing
        # starts (run_simple starts the trace), so only the requests are traced.
        app = create_app(TestConfig)
        with app.app_context():
            db.create_all()
            client = app.test_client()
            rand_id = random.randint(1000, 9999)

            # Warmup (untraced): resolve lazy imports + routing so importlib
            # machinery (ModuleSpec, ...) doesn't dominate the traced diagram.
            try:
                client.get('/api/articles')
            except Exception:
                pass

            # No-self closure: references client/rand_id only, so the traced
            # request stack's outermost caller is External_User, not the runner.
            def action():
                client.post('/api/users', json={
                    "user": {
                        "username": f"thesis_{rand_id}",
                        "email": f"test_{rand_id}@example.com",
                        "password": "password123",
                    }
                })
                client.get('/api/articles')

            return run_simple(filter_engine, action)
