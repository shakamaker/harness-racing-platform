"""Par-times materialized view binding.

The underlying object is the ``mv_par_times`` materialized view created by
``sql/schema.sql``. The Table below exists so the query layer can join it like
any other entity, but SQLAlchemy must not emit CREATE/DROP for it — schema.sql
owns the DDL.

We install ``before_create`` / ``before_drop`` event listeners that return
``False`` so ``Base.metadata.create_all()`` / ``drop_all()`` skip this Table.

No declarative ORM class is exposed for this view: an ORM class over a
multi-column nullable PK is an identity-map hazard (two rows with NULLs in
filter columns collide on identity). Queries should use Core ``select()``
against ``mv_par_times_table`` and project to ``ParTimesRead``.

Refresh is the API service's responsibility (nightly cron):

    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_par_times;
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, Numeric, Table, event

from .base import Base


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
    Column("gross_sample_size", Integer),
    Column("lead_sample_size", Integer),
    Column("mile_sample_size", Integer),
    Column("computed_at", DateTime(timezone=True)),
)


@event.listens_for(mv_par_times_table, "before_create")
def _skip_view_create(target, connection, **kw):  # type: ignore[no-untyped-def]
    return False


@event.listens_for(mv_par_times_table, "before_drop")
def _skip_view_drop(target, connection, **kw):  # type: ignore[no-untyped-def]
    return False


__all__ = ["mv_par_times_table"]
