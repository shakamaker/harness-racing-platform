"""Public API for the harness_models package.

Importing this module forces every ORM class to register itself with
``Base.metadata`` so that ``Base.metadata.create_all(engine)`` and Alembic
autogenerate both see the complete schema.
"""

from __future__ import annotations

from .base import Base
from .horses import Horse
from .logs import LogLevel, ParseDLQ, PipelineLog, PipelineStage, ScrapeDLQ
from .lookups import (
    AgeClass,
    Country,
    HorseSex,
    RaceClass,
    RaceGait,
    RaceType,
    StartType,
    State,
    StewardsCode,
    Surface,
    TrackCondition,
)
from .meetings import DayNight, MeetingStatus, RaceMeeting
from .pars import MvParTimes, mv_par_times_table
from .people import Person
from .races import Race
from .runners import Runner
from .stewards import StewardsComment, StewardsCommentCode
from .time_utils import format_ss_ms, to_ss_ms
from .times import RaceTime
from .tracks import RaceTrack

__all__ = [
    # ORM base
    "Base",
    # Lookups
    "AgeClass",
    "Country",
    "HorseSex",
    "RaceClass",
    "RaceGait",
    "RaceType",
    "StartType",
    "State",
    "StewardsCode",
    "Surface",
    "TrackCondition",
    # Core entities
    "Horse",
    "Person",
    "Race",
    "RaceMeeting",
    "RaceTime",
    "RaceTrack",
    "Runner",
    "StewardsComment",
    "StewardsCommentCode",
    # Workflow enums
    "DayNight",
    "MeetingStatus",
    # Materialized view
    "MvParTimes",
    "mv_par_times_table",
    # Logging
    "LogLevel",
    "ParseDLQ",
    "PipelineLog",
    "PipelineStage",
    "ScrapeDLQ",
    # Time utilities
    "format_ss_ms",
    "to_ss_ms",
]
