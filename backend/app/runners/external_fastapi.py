"""
Runner for the FastAPI demo app (applications/fastapi_demo/app.py).

This replaces the vendored RealWorld FastAPI clone, which cannot run alongside a
modern FastAPI (the backend server needs a current FastAPI; the vendored app needs
FastAPI ~0.79 + Pydantic v1 — two versions of the `fastapi` package can't coexist
in one interpreter, on any Python version).

We trace the app's business layers directly — TaskController → TaskService →
TaskRepository, plus the Validator utility — the same way the console-app runners
invoke their targets by direct method call (not over the network). Going through
the HTTP TestClient instead would bury these layers ~30 frames deep under
Starlette, where the dynamic depth filter (Stage 2) removes exactly the app code
we want to show. The app is still a real FastAPI service (routes + Pydantic v2
models in app.py); we exercise its controller boundary.
"""
from .base import PROJECT_ROOT, RunOutcome, run_simple  # noqa: F401
from src.filter import ArchitectureFilter

from applications.fastapi_demo.app import TaskController, TaskIn


class ExternalFastAPIRunner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        # No-self closure so the controller's caller is External_User.
        def action():
            controller = TaskController()
            controller.list_tasks()
            controller.get_task(1)
            controller.get_task(2)
            controller.create_task(TaskIn(title="Deploy portfolio", priority=2))
            controller.create_task(TaskIn(title="Write README", priority=1))

        return run_simple(filter_engine, action)
