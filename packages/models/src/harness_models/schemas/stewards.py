"""Stewards-comment DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ._base import BaseSchema


class StewardsCommentUpsert(BaseSchema):
    runner_id: int
    full_text: str | None = None
    code_ids: list[int] = Field(default_factory=list)


class StewardsCommentRead(BaseSchema):
    runner_id: int
    full_text: str | None
    created_at: datetime
    code_ids: list[int] = Field(default_factory=list)


__all__ = ["StewardsCommentRead", "StewardsCommentUpsert"]
