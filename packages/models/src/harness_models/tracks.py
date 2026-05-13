"""Race tracks — physical venues hosting meetings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col

if TYPE_CHECKING:
    from .lookups import State, Surface
    from .meetings import RaceMeeting


class RaceTrack(Base):
    __tablename__ = "race_tracks"
    __table_args__ = (
        UniqueConstraint("track_name", "state_id", name="uq_race_tracks_name_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_name: Mapped[str] = mapped_column(index=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id"), index=True)
    surface_id: Mapped[int | None] = mapped_column(ForeignKey("surfaces.id"), default=None)
    created_at: Mapped[created_at_col]

    state: Mapped["State"] = relationship(lazy="joined")
    surface: Mapped["Surface | None"] = relationship(lazy="joined")
    meetings: Mapped[list["RaceMeeting"]] = relationship(
        back_populates="track", cascade="save-update, merge"
    )


__all__ = ["RaceTrack"]
