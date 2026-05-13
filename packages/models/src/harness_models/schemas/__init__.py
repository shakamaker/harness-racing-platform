"""Pydantic v2 schemas — request/response DTOs for the parser and API."""

from __future__ import annotations

from ._base import BaseSchema
from .horses import HorseRead, HorseUpsert
from .logs import DLQItemRead, PipelineLogCreate, PipelineLogRead
from .meetings import MeetingCreate, MeetingRead, MeetingUpdate
from .pars import ParTimesRead
from .people import PersonRead, PersonUpsert
from .races import RaceCreate, RaceRead, RaceSummary
from .runners import RunnerCreate, RunnerRead
from .stewards import StewardsCommentRead, StewardsCommentUpsert
from .times import RaceTimeCreate, RaceTimeRead
from .tracks import TrackCreate, TrackRead

__all__ = [
    "BaseSchema",
    "DLQItemRead",
    "HorseRead",
    "HorseUpsert",
    "MeetingCreate",
    "MeetingRead",
    "MeetingUpdate",
    "ParTimesRead",
    "PersonRead",
    "PersonUpsert",
    "PipelineLogCreate",
    "PipelineLogRead",
    "RaceCreate",
    "RaceRead",
    "RaceSummary",
    "RaceTimeCreate",
    "RaceTimeRead",
    "RunnerCreate",
    "RunnerRead",
    "StewardsCommentRead",
    "StewardsCommentUpsert",
    "TrackCreate",
    "TrackRead",
]
