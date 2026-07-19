"""
Single source of truth mapping app_id -> runner + metadata.

Consumed by GET /api/apps (listing) and POST /api/trace (dispatch). Runner
modules are imported lazily inside _build_registry() so that importing this
module (e.g. for the app list) doesn't eagerly pull in every heavy target
framework; the registry is built once on first access and cached.
"""
from dataclasses import dataclass
from typing import Dict, Optional

from .base import AppRunner


@dataclass(frozen=True)
class AppMeta:
    id: str
    display_name: str
    category: str  # "console" | "external"
    description: str
    runner: AppRunner


_REGISTRY: Optional[Dict[str, AppMeta]] = None


def _build_registry() -> Dict[str, AppMeta]:
    from .console_app_1 import ConsoleApp1Runner
    from .console_app_2 import ConsoleApp2Runner
    from .console_app_3 import ConsoleApp3Runner
    from .external_flask import ExternalFlaskRunner
    from .external_fastapi import ExternalFastAPIRunner
    from .external_django import ExternalDjangoRunner
    from .external_homeassistant import ExternalHomeAssistantRunner
    from .external_zulip import ExternalZulipRunner

    metas = [
        AppMeta("console_app_1", "Sorter", "console",
                "A merge-sort pipeline with layered classes (controller, data, "
                "logic, stats) plus logger/validator utilities — the canonical "
                "demo showing each filter stage stripping noise.",
                ConsoleApp1Runner()),
        AppMeta("console_app_2", "Bank Simulation", "console",
                "A multi-threaded bank simulation (parallel user sessions). "
                "Demonstrates tracing across threads via threading.settrace().",
                ConsoleApp2Runner()),
        AppMeta("console_app_3", "ETL Pipeline", "console",
                "An extract-transform-load pipeline (source → transformer → "
                "warehouse). A clean three-layer flow.",
                ConsoleApp3Runner()),
        AppMeta("external_flask", "Flask RealWorld", "external",
                "The Conduit RealWorld API on Flask + SQLAlchemy. Traces user "
                "registration and article listing through the full request stack.",
                ExternalFlaskRunner()),
        AppMeta("external_fastapi", "FastAPI Demo", "external",
                "A compact layered FastAPI service (controller → service → "
                "repository, plus a validator utility). Traces list/get/create "
                "task requests through the full stack.",
                ExternalFastAPIRunner()),
        AppMeta("external_django", "Django RealWorld", "external",
                "The Conduit RealWorld API on Django + DRF. Ten read-only API "
                "scenarios; capped at 500 events (Django's stack is deep).",
                ExternalDjangoRunner()),
        AppMeta("external_homeassistant", "Home Assistant Core", "external",
                "Home Assistant's core event/state/service bus. Eight synthetic "
                "scenarios (set state, register/call service, fire events).",
                ExternalHomeAssistantRunner()),
        AppMeta("external_zulip", "Zulip API Client", "external",
                "The Zulip Python API client. Ten client operations (send, "
                "profile, subscribe, render, …) with all HTTP mocked.",
                ExternalZulipRunner()),
    ]
    return {m.id: m for m in metas}


def get_registry() -> Dict[str, AppMeta]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_runner(app_id: str) -> Optional[AppMeta]:
    return get_registry().get(app_id)
