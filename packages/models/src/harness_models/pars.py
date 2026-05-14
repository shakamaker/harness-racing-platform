"""Par-times materialized view binding (read-only).

This is NOT a real table — the underlying object is the ``mv_par_times``
materialized view created by ``sql/schema.sql``. The ORM class binds to it
purely so query layers can join it like any other entity. SQLAlchemy will not
emit CREATE/DROP for this Table because ``info["is_view"] = True`` and we use
``__table__`` instead of declarative ``__tablename__``.

Refresh is the API service's responsibility (nightly cron):

    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_par_times;
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Integer, Numeric, Table
from sqlalchemy.orm import Mapped, relationship

from .base import Base

if TYPE_CHECKING:
    from .lookups import AgeClass, RaceClass, RaceGait, StartType, TrackCondition
    from .tracks import RaceTrack


mv_par_times_table = Table(
    "mv_par_times",
    Base.metadata,
    Column("track_id", Integer, primary_key=True),
    Column("distance_m", Integer, primary_key=True),
    Column("race_gait_id", Integer, primary_key=True),
    Column("start_type_id", Integer, primary_key=True),
    Column("track_condition_id", Integer, nullable=True, primary_key=True),
    Column("race_class_id", Integer, nullable=True, primary_key=True),
    Column("age_class_id", Integer, nullable=True, primary_key=True),
    Column("par_gross_time_s", Numeric(8, 3)),
    Column("par_lead_time_s", Numeric(8, 3)),
    Column("par_mile_rate_s", Numeric(8, 3)),
    Column("sample_size", Integer),
    Column("computed_at", DateTime(timezone=True)),
    info={"is_view": True},
)


class MvParTimes(Base):
    """Read-only ORM binding to ``mv_par_times``."""

    __table__ = mv_par_times_table

    track_id: Mapped[int]
    distance_m: Mapped[int]
    race_gait_id: Mapped[int]
    start_type_id: Mapped[int]
    track_condition_id: Mapped[int | None]
    race_class_id: Mapped[int | None]
    age_class_id: Mapped[int | None]
    par_gross_time_s: Mapped[Decimal | None]
    par_lead_time_s: Mapped[Decimal | None]
    par_mile_rate_s: Mapped[Decimal | None]
    sample_size: Mapped[int]
    computed_at: Mapped[datetime]

    track: Mapped["RaceTrack"] = relationship(
        primaryjoin="MvParTimes.track_id == RaceTrack.id",
        foreign_keys=[mv_par_times_table.c.track_id],
        viewonly=True,
    )
    race_gait: Mapped["RaceGait"] = relationship(
        primaryjoin="MvParTimes.race_gait_id == RaceGait.id",
        foreign_keys=[mv_par_times_table.c.race_gait_id],
        viewonly=True,
    )
    start_type: Mapped["StartType"] = relationship(
        primaryjoin="MvParTimes.start_type_id == StartType.id",
        foreign_keys=[mv_par_times_table.c.start_type_id],
        viewonly=True,
    )
    track_condition: Mapped["TrackCondition | None"] = relationship(
        primaryjoin="MvParTimes.track_condition_id == TrackCondition.id",
        foreign_keys=[mv_par_times_table.c.track_condition_id],
        viewonly=True,
    )
    race_class: Mapped["RaceClass | None"] = relationship(
        primaryjoin="MvParTimes.race_class_id == RaceClass.id",
        foreign_keys=[mv_par_times_table.c.race_class_id],
        viewonly=True,
    )
    age_class: Mapped["AgeClass | None"] = relationship(
        primaryjoin="MvParTimes.age_class_id == AgeClass.id",
        foreign_keys=[mv_par_times_table.c.age_class_id],
        viewonly=True,
    )


__all__ = ["MvParTimes", "mv_par_times_table"]
