"""Race meetings — one race card per (track, date)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col, updated_at_col

if TYPE_CHECKING:
    from .races import Race
    from .tracks import RaceTrack


class MeetingStatus(str, Enum):
    PENDING_DOWNLOAD = "PENDING_DOWNLOAD"
    DOWNLOADED = "DOWNLOADED"
    PARSED = "PARSED"
    FAILED = "FAILED"


class DayNight(str, Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    TWILIGHT = "TWILIGHT"
    UNKNOWN = "UNKNOWN"


class RaceMeeting(Base):
    __tablename__ = "race_meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_code: Mapped[str] = mapped_column(String(32), unique=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("race_tracks.id", ondelete="RESTRICT"), index=True
    )
    meeting_date: Mapped[date] = mapped_column(index=True)
    day_night: Mapped[DayNight] = mapped_column(
        SAEnum(DayNight, name="day_night", native_enum=True, create_type=False),
        default=DayNight.UNKNOWN,
    )
    meeting_url: Mapped[str | None] = mapped_column(String(512), default=None)
    html_path: Mapped[str | None] = mapped_column(String(512), default=None)
    status: Mapped[MeetingStatus] = mapped_column(
        SAEnum(MeetingStatus, name="meeting_status", native_enum=True, create_type=False),
        default=MeetingStatus.PENDING_DOWNLOAD,
        index=True,
    )
    scraped_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[created_at_col]
    updated_at: Mapped[updated_at_col]

    track: Mapped["RaceTrack"] = relationship(back_populates="meetings", lazy="joined")
    races: Mapped[list["Race"]] = relationship(
        back_populates="meeting", cascade="save-update, merge"
    )


__all__ = ["DayNight", "MeetingStatus", "RaceMeeting"]
