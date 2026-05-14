"""Horse DTOs."""

from __future__ import annotations

from datetime import datetime

from ._base import BaseSchema


class HorseUpsert(BaseSchema):
    """Parser upsert payload. ``horse_id`` is the source-system id."""

    horse_id: int
    horse_name: str
    sex_id: int | None = None
    foaled: int | None = None
    sire_id: int | None = None
    dam_id: int | None = None


class HorseRead(BaseSchema):
    horse_id: int
    horse_name: str
    sex_id: int | None
    foaled: int | None
    sire_id: int | None
    dam_id: int | None
    created_at: datetime
    updated_at: datetime


__all__ = ["HorseRead", "HorseUpsert"]
