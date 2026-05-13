"""Stewards-comment DTOs."""

from __future__ import annotations

from datetime import datetime

from ._base import BaseSchema


class StewardsCommentUpsert(BaseSchema):
    runner_id: int
    full_text: str | None = None
    code_ids: list[int] = []


class StewardsCommentRead(BaseSchema):
    runner_id: int
    full_text: str | None
    created_at: datetime
    code_ids: list[int] = []


__all__ = ["StewardsCommentRead", "StewardsCommentUpsert"]
