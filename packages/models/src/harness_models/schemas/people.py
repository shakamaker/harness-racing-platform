"""Person DTOs (trainers + drivers share this table)."""

from __future__ import annotations

from datetime import datetime

from ._base import BaseSchema, LinkToken


class PersonUpsert(BaseSchema):
    name: str
    link_token: LinkToken


class PersonRead(BaseSchema):
    id: int
    name: str
    link_token: LinkToken
    created_at: datetime


__all__ = ["PersonRead", "PersonUpsert"]
