"""Meeting DTOs."""

from __future__ import annotations

from datetime import date, datetime

from ..meetings import DayNight, MeetingStatus
from ._base import BaseSchema


class MeetingCreate(BaseSchema):
    meeting_code: str
    track_id: int
    meeting_date: date
    day_night: DayNight = DayNight.UNKNOWN
    meeting_url: str | None = None
    html_path: str | None = None
    status: MeetingStatus = MeetingStatus.PENDING_DOWNLOAD


class MeetingUpdate(BaseSchema):
    day_night: DayNight | None = None
    meeting_url: str | None = None
    html_path: str | None = None
    status: MeetingStatus | None = None
    scraped_at: datetime | None = None


class MeetingRead(BaseSchema):
    id: int
    meeting_code: str
    track_id: int
    meeting_date: date
    day_night: DayNight
    meeting_url: str | None
    html_path: str | None
    status: MeetingStatus
    scraped_at: datetime | None
    created_at: datetime
    updated_at: datetime


__all__ = ["MeetingCreate", "MeetingRead", "MeetingUpdate"]
