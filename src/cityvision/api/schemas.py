from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from cityvision.domain.statuses import EventStatus, WorkOrderStatus


class StatusUpdate(BaseModel):
    status: EventStatus = Field(..., examples=["confirmed", "false_positive", "under_review"])


class WorkOrderCreate(BaseModel):
    unit: str = Field(..., examples=["yol_bakim", "temizlik"])
    note: str = ""


class WorkOrderUpdate(BaseModel):
    status: Optional[WorkOrderStatus] = Field(
        None, examples=["created", "assigned", "in_progress", "resolved"]
    )
    note: Optional[str] = None
    assignee: Optional[str] = None


class IngestBody(BaseModel):
    run_dir: str


class ZonesIngestBody(BaseModel):
    path: str = Field(..., examples=["configs/zones.example.geojson"])


REVIEW_REASONS = frozenset(
    {"manhole", "shadow", "vehicle", "marking", "vegetation", "duplicate", "other"}
)


class ReviewBody(BaseModel):
    label: str = Field(..., examples=["correct", "wrong", "unsure", "work_order", "resolved"])
    # Why a candidate was rejected; only meaningful with label "wrong".
    reason: Optional[str] = Field(None, examples=sorted(REVIEW_REASONS))
    note: str = ""
    reviewer: str = "operator"
    unit: str = "ops"


class VehicleBody(BaseModel):
    id: str
    name: Optional[str] = None
    plate: Optional[str] = None
    route_id: Optional[str] = None


class CameraBody(BaseModel):
    id: str
    vehicle_id: Optional[str] = None
    label: Optional[str] = None
    facing: Optional[str] = None


class RouteBody(BaseModel):
    id: str
    name: str
    city: str = "erzurum"
    coordinates: Optional[List[List[float]]] = None  # [[lon, lat], ...]
