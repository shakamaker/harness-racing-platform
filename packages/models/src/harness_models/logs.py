"""Unified pipeline log + per-stage dead-letter queues."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PipelineStage(str, Enum):
    SCRAPE = "SCRAPE"
    PARSE = "PARSE"
    TRANSFORM = "TRANSFORM"
    API = "API"


class PipelineLog(Base):
    __tablename__ = "pipeline_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[created_at_col]
    stage: Mapped[PipelineStage] = mapped_column(
        SAEnum(PipelineStage, name="pipeline_stage", native_enum=True, create_type=False),
    )
    agent: Mapped[str] = mapped_column(String(32))
    module: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    level: Mapped[LogLevel] = mapped_column(
        SAEnum(LogLevel, name="log_level", native_enum=True, create_type=False),
        default=LogLevel.INFO,
    )
    meeting_code: Mapped[str | None] = mapped_column(String(32), default=None)
    race_number: Mapped[int | None] = mapped_column(default=None)
    horse_id: Mapped[int | None] = mapped_column(default=None)
    attempt: Mapped[int] = mapped_column(default=1)
    latency_ms: Mapped[int | None] = mapped_column(default=None)
    outcome: Mapped[str] = mapped_column(String(64), default="")
    payload_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    # Error-only columns
    stack_trace: Mapped[str | None] = mapped_column(default=None)
    offending_html: Mapped[str | None] = mapped_column(default=None)
    last_checkpoint: Mapped[str | None] = mapped_column(String(255), default=None)
    triaged: Mapped[bool] = mapped_column(default=False)


class ScrapeDLQ(Base):
    __tablename__ = "scrape_dlq"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[created_at_col]
    meeting_code: Mapped[str | None] = mapped_column(String(32), default=None)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    error_log_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("pipeline_log.id", ondelete="SET NULL"),
        default=None,
    )
    reprocessed: Mapped[bool] = mapped_column(default=False)
    reprocessed_at: Mapped[datetime | None] = mapped_column(default=None)

    error_log: Mapped["PipelineLog | None"] = relationship(foreign_keys=[error_log_id])


class ParseDLQ(Base):
    __tablename__ = "parse_dlq"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[created_at_col]
    meeting_code: Mapped[str | None] = mapped_column(String(32), default=None)
    race_number: Mapped[int | None] = mapped_column(default=None)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    error_log_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("pipeline_log.id", ondelete="SET NULL"),
        default=None,
    )
    reprocessed: Mapped[bool] = mapped_column(default=False)
    reprocessed_at: Mapped[datetime | None] = mapped_column(default=None)

    error_log: Mapped["PipelineLog | None"] = relationship(foreign_keys=[error_log_id])


__all__ = [
    "LogLevel",
    "ParseDLQ",
    "PipelineLog",
    "PipelineStage",
    "ScrapeDLQ",
]
