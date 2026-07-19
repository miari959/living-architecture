"""Pydantic request/response models for the API (Pydantic v2)."""
from typing import Dict, List

from pydantic import BaseModel, Field


class AppInfo(BaseModel):
    id: str
    display_name: str
    category: str  # "console" | "external"
    description: str


class TraceRequest(BaseModel):
    app_id: str
    stage1: bool = True
    stage2: bool = True
    stage3: bool = True
    stage4: bool = True


class TraceStats(BaseModel):
    total_events: int
    kept: int
    removed: int
    reduction_pct: float
    stage1_removed: int
    stage2_removed: int
    stage3_removed: int
    layer_breakdown: Dict[str, int] = Field(default_factory=dict)


class TraceResult(BaseModel):
    app_id: str
    mermaid: str
    stats: TraceStats
    warnings: List[str] = Field(default_factory=list)
    empty: bool = False
    duration_ms: float = 0.0
