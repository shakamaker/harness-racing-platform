"""Pydantic v2 DTOs emitted by the parser (CLAUDE.md §4.2.4).

These intentionally mirror the SQL schema in ``sql/shit_schema.sql`` so the
JSON snapshot can be replayed into the ORM once Agent 3 lands it. Keep
serialisation simple — ``BaseModel.model_dump(mode="json")`` produces the
shape the database lane consumes.

Idempotency keys (per spec):

* meeting: ``meeting_code``
* race:    ``(meeting_code, race_number)``
* runner:  ``(meeting_code, race_number, horse_id)``
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DayNight = Literal["DAY", "NIGHT", "TWILIGHT", "UNKNOWN"]


class _BaseDTO(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=False,
        populate_by_name=True,
    )


class StewardsCommentDTO(_BaseDTO):
    codes: list[str] = Field(default_factory=list)
    """Short codes from the visible span text (e.g. ``["GS", "L", "1"]``)."""

    full_text: str | None = None
    """The tooltip body from ``data-original-title``."""


class RaceTimesDTO(_BaseDTO):
    track_rating: str | None = None
    gross_time_display: str | None = None
    gross_time_s: float | None = None
    lead_time_display: str | None = None
    lead_time_s: float | None = None
    mile_rate_display: str | None = None
    mile_rate_s: float | None = None
    q1_display: str | None = None
    q1_s: float | None = None
    q2_display: str | None = None
    q2_s: float | None = None
    q3_display: str | None = None
    q3_s: float | None = None
    q4_display: str | None = None
    q4_s: float | None = None
    first_half_s: float | None = None
    """Calculated: ``q1_s + q2_s`` when both are present."""
    second_half_s: float | None = None
    """Calculated: ``q3_s + q4_s`` when both are present."""
    margin1: float | None = None
    margin2: float | None = None


class RunnerDTO(_BaseDTO):
    horse_id: int
    horse_name: str
    runner_number: int | None = None
    barrier_raw: str | None = None
    """The full barrier string as printed (e.g. ``"Fr7"``, ``"1A"``, ``"FP"``)."""
    barrier: int | None = None
    """The integer extracted from ``barrier_raw`` (e.g. ``7`` from ``"Fr7"``).
    ``None`` when no integer is present (``"FP"``, ``"SR"``)."""
    finish_position: int | None = None
    """``None`` for scratched / DNF / null-run finishers."""
    raw_margin: str | None = None
    adjusted_margin: float | None = None
    null_run: bool = False
    scratched: bool = False
    stake: float | None = None
    raw_price: str | None = None
    starting_price: float | None = None
    trainer_name: str | None = None
    trainer_link_token: str | None = None
    driver_name: str | None = None
    driver_link_token: str | None = None
    stewards: StewardsCommentDTO | None = None


class RaceDTO(_BaseDTO):
    race_number: int
    race_name: str | None = None
    race_time: str | None = None
    """Local clock time of the race (e.g. ``"5:45pm"``)."""
    race_distance_m: int | None = None
    race_type: str | None = None
    """e.g. ``"PBD/NR"``, ``"RBD"``, ``"FFA"`` — derived from the conditions text."""
    class_name: str | None = None
    """e.g. ``"NR up to 45"``, ``"R0 Only"`` — primary class restriction."""
    age_class: str | None = None
    """e.g. ``"4YO and older"``, ``"3YO & OLDER"``."""
    race_purse: float | None = None
    start_type: str | None = None
    """``"Mobile"`` / ``"Standing Start"`` typically."""
    race_gait: str | None = None
    """``"PACERS"`` / ``"TROTTERS"``."""
    is_final: bool = True
    times: RaceTimesDTO | None = None
    runners: list[RunnerDTO] = Field(default_factory=list)


class MeetingDTO(_BaseDTO):
    meeting_code: str
    track_name: str
    state: str
    meeting_date: date
    day_night: DayNight = "UNKNOWN"
    races: list[RaceDTO] = Field(default_factory=list)

    @field_validator("state")
    @classmethod
    def _lower_state(cls, v: str) -> str:
        return v.lower()


__all__ = [
    "DayNight",
    "MeetingDTO",
    "RaceDTO",
    "RaceTimesDTO",
    "RunnerDTO",
    "StewardsCommentDTO",
]
