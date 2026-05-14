"""Pipeline-log + DLQ DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..logs import LogLevel, PipelineStage
from ._base import BaseSchema


class PipelineLogCreate(BaseSchema):
    stage: PipelineStage
    agent: str
    module: str
    action: str
    level: LogLevel = LogLevel.INFO
    meeting_code: str | None = None
    race_number: int | None = None
    horse_id: int | None = None
    attempt: int = 1
    latency_ms: int | None = None
    outcome: str
    payload_hash: str | None = None
    payload: dict[str, Any] | None = None
    stack_trace: str | None = None
    offending_html: str | None = None
    last_checkpoint: str | None = None


class PipelineLogRead(BaseSchema):
    id: int
    ts: datetime
    stage: PipelineStage
    agent: str
    module: str
    action: str
    level: LogLevel
    meeting_code: str | None
    race_number: int | None
    horse_id: int | None
    attempt: int
    latency_ms: int | None
    outcome: str
    payload_hash: str | None
    payload: dict[str, Any] | None
    stack_trace: str | None
    offending_html: str | None
    last_checkpoint: str | None
    triaged: bool


class DLQItemRead(BaseSchema):
    id: int
    ts: datetime
    meeting_code: str | None
    race_number: int | None = None
    payload: dict[str, Any] | None
    error_log_id: int | None
    reprocessed: bool
    reprocessed_at: datetime | None


__all__ = ["DLQItemRead", "PipelineLogCreate", "PipelineLogRead"]
