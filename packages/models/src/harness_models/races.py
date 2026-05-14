"""Race — one event within a meeting."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col, updated_at_col

if TYPE_CHECKING:
    from .lookups import AgeClass, RaceClass, RaceGait, RaceType, StartType, TrackCondition
    from .meetings import RaceMeeting
    from .runners import Runner
    from .times import RaceTime


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (
        UniqueConstraint("meeting_id", "race_number", name="uq_races_meeting_race_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("race_meetings.id", ondelete="RESTRICT")
    )
    race_number: Mapped[int]
    race_name: Mapped[str | None] = mapped_column(String(255), default=None)
    distance_m: Mapped[int | None] = mapped_column(default=None)
    race_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("race_types.id"), default=None
    )
    # Rows with NULL race_gait_id or start_type_id are excluded from par-time
    # computation (mv_par_times filters them out).
    race_gait_id: Mapped[int | None] = mapped_column(
        ForeignKey("race_gaits.id"), default=None
    )
    start_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("start_types.id"), default=None
    )
    race_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("race_classes.id"), default=None
    )
    age_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("age_classes.id"), default=None
    )
    race_purse: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    track_condition_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_conditions.id"), default=None
    )
    # Free-text race time as printed on the source card (e.g. "12:45"). The
    # canonical numeric times live on race_times.
    race_time_str: Mapped[str | None] = mapped_column(default=None)
    is_final: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[created_at_col]
    updated_at: Mapped[updated_at_col]

    meeting: Mapped["RaceMeeting"] = relationship(back_populates="races")
    race_type: Mapped["RaceType | None"] = relationship(lazy="joined")
    race_gait: Mapped["RaceGait | None"] = relationship(lazy="joined")
    start_type: Mapped["StartType | None"] = relationship(lazy="joined")
    race_class: Mapped["RaceClass | None"] = relationship(lazy="joined")
    age_class: Mapped["AgeClass | None"] = relationship(lazy="joined")
    track_condition: Mapped["TrackCondition | None"] = relationship(lazy="joined")
    times: Mapped["RaceTime | None"] = relationship(
        back_populates="race", uselist=False, cascade="all, delete-orphan"
    )
    runners: Mapped[list["Runner"]] = relationship(
        back_populates="race", cascade="save-update, merge"
    )


__all__ = ["Race"]
