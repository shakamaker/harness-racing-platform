"""Structured-JSON logging setup (CLAUDE.md §5.1).

Every log entry carries: ts, level, agent, module, action, meeting_code?,
race_number?, horse_id?, attempt?, latency_ms?, outcome?, payload_hash?.
Use ``get_logger(__name__).bind(meeting_code=..., action=...)`` at the
top of each unit of work and call ``log.info("downloaded", outcome="ok",
latency_ms=elapsed)`` etc.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


def configure_logging(*, level: str | None = None, json: bool | None = None) -> None:
    """Idempotent structlog configuration.

    Re-calling overwrites the previous config — useful for tests that want a
    capture handler.
    """
    log_level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = logging.getLevelNamesMapping().get(log_level_name, logging.INFO)
    use_json = json if json is not None else os.getenv("LOG_FORMAT", "json").lower() == "json"

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: Any
    if use_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Return a structlog logger bound with ``agent="scraper"`` and ``module``."""
    return structlog.get_logger().bind(agent="scraper", module=name or "harness_scraper")
