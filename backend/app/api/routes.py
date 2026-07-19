"""API routes: health, app listing, and trace execution."""
from fastapi import APIRouter, HTTPException

from ..core import trace_lock, trace_service
from ..runners.registry import get_registry
from .schemas import AppInfo, TraceRequest, TraceResult

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok", "queue_depth": trace_lock.queue_depth()}


@router.get("/apps", response_model=list[AppInfo])
async def list_apps():
    return [
        AppInfo(
            id=m.id,
            display_name=m.display_name,
            category=m.category,
            description=m.description,
        )
        for m in get_registry().values()
    ]


@router.post("/trace", response_model=TraceResult)
async def run_trace(req: TraceRequest):
    if get_registry().get(req.app_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown app_id: {req.app_id}")

    try:
        result = await trace_service.run_trace(
            req.app_id, req.stage1, req.stage2, req.stage3, req.stage4
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown app_id: {req.app_id}")
    except Exception as e:  # noqa: BLE001 - surface as 500 with a clean message
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    return result
