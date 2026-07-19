"""
A compact, purpose-built FastAPI application used as a live tracing target.

It replaces the vendored RealWorld FastAPI clone, which is built on Pydantic v1
and cannot run on Python 3.14 (v1's annotation inference is broken by PEP 649's
lazy annotations). This app uses Pydantic v2 and runs cleanly on 3.14.

It is deliberately layered so the trace produces a readable architecture:

    Route handler → TaskController → TaskService → TaskRepository

with a shared Validator utility (high fan-in, low fan-out) that the Stage 1b
filter is meant to strip. This mirrors the pedagogical shape of the console demos
while exercising a real FastAPI request stack via the test client.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# --------------------------------------------------------------------------
# Domain model (Pydantic v2)
# --------------------------------------------------------------------------
class TaskIn(BaseModel):
    title: str
    priority: int = 1


# --------------------------------------------------------------------------
# Data layer
# --------------------------------------------------------------------------
class TaskRepository:
    """Persistence layer (in-memory)."""

    def __init__(self):
        self._tasks = [
            {"id": 1, "title": "Write thesis", "priority": 3},
            {"id": 2, "title": "Build web frontend", "priority": 2},
        ]
        self._next_id = 3

    def list_all(self):
        return list(self._tasks)

    def get(self, task_id):
        for t in self._tasks:
            if t["id"] == task_id:
                return t
        return None

    def add(self, title, priority):
        task = {"id": self._next_id, "title": title, "priority": priority}
        self._tasks.append(task)
        self._next_id += 1
        return task


# --------------------------------------------------------------------------
# Utility (high fan-in / low fan-out -> Stage 1b target)
# --------------------------------------------------------------------------
class Validator:
    """Shared validation utility, called from several service methods."""

    def is_valid_title(self, title):
        return bool(title) and len(title.strip()) > 0

    def is_valid_id(self, task_id):
        return isinstance(task_id, int) and task_id > 0


# --------------------------------------------------------------------------
# Business logic layer
# --------------------------------------------------------------------------
class TaskService:
    """Logic layer: orchestrates validation and persistence."""

    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator

    def list_tasks(self):
        return self.repository.list_all()

    def get_task(self, task_id):
        if not self.validator.is_valid_id(task_id):
            return None
        return self.repository.get(task_id)

    def create_task(self, title, priority):
        if not self.validator.is_valid_title(title):
            raise ValueError("Invalid title")
        return self.repository.add(title, priority)


# --------------------------------------------------------------------------
# Presentation / control layer
# --------------------------------------------------------------------------
class TaskController:
    """Presentation layer: bridges HTTP routes and the service."""

    def __init__(self):
        self.service = TaskService(TaskRepository(), Validator())

    def list_tasks(self):
        return self.service.list_tasks()

    def get_task(self, task_id):
        task = self.service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def create_task(self, payload: TaskIn):
        try:
            return self.service.create_task(payload.title, payload.priority)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


def create_app() -> FastAPI:
    app = FastAPI(title="FastAPI Demo (Living Architecture)")
    controller = TaskController()

    @app.get("/tasks")
    def list_tasks():
        return controller.list_tasks()

    @app.get("/tasks/{task_id}")
    def get_task(task_id: int):
        return controller.get_task(task_id)

    @app.post("/tasks")
    def create_task(task: TaskIn):
        return controller.create_task(task)

    return app


app = create_app()
