"""Race DTOs. ``RaceRead`` is the deep response shape used by /races/{id}."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ._base import BaseSchema
from .runners import RunnerRead
from .times import RaceTimeRead


class RaceCreate(BaseSchema):
    meeting_id: int
    race_number: int
    race_name: str | None = None
    distance_m: int | None = None
    race_type_id: int | None = None
    race_gait_id: int | None = None
    start_type_id: int | None = None
    race_class_id: int | None = None
    age_class_id: int | None = None
    race_purse: Decimal | None = None
    track_condition_id: int | None = None
    race_time_str: str | None = None
    is_final: bool = True


class RaceSummary(BaseSchema):
    id: int
    meeting_id: int
    race_number: int
    race_name: str | None
    distance_m: int | None
    is_final: bool


class RaceRead(BaseSchema):
    id: int
    meeting_id: int
    race_number: int
    race_name: str | None
    distance_m: int | None
    race_type_id: int | None
    race_gait_id: int | None
    start_type_id: int | None
    race_class_id: int | None
    age_class_id: int | None
    race_purse: Decimal | None
    track_condition_id: int | None
    race_time_str: str | None
    is_final: bool
    created_at: datetime
    updated_at: datetime
    times: RaceTimeRead | None = None
    runners: list[RunnerRead] = []


__all__ = ["RaceCreate", "RaceRead", "RaceSummary"]
