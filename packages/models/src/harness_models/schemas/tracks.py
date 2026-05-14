"""Track DTOs."""

from __future__ import annotations

from datetime import datetime

from ._base import BaseSchema


class TrackCreate(BaseSchema):
    track_name: str
    state_id: int
    surface_id: int | None = None


class TrackRead(BaseSchema):
    id: int
    track_name: str
    state_id: int
    surface_id: int | None
    created_at: datetime


__all__ = ["TrackCreate", "TrackRead"]
