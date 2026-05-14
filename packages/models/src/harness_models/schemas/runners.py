"""Runner DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ._base import BaseSchema


class RunnerCreate(BaseSchema):
    race_id: int
    horse_id: int
    runner_number: int | None = None
    barrier: int | None = None
    barrier_raw: str | None = None
    trainer_id: int | None = None
    driver_id: int | None = None
    finish_position: int | None = None
    raw_margin: str | None = None
    adjusted_margin: Decimal | None = None
    null_run: bool = False
    scratched: bool = False
    stake: Decimal | None = None
    raw_price: str | None = None
    starting_price: Decimal | None = None


class RunnerRead(BaseSchema):
    id: int
    race_id: int
    horse_id: int
    runner_number: int | None
    barrier: int | None
    barrier_raw: str | None
    trainer_id: int | None
    driver_id: int | None
    finish_position: int | None
    raw_margin: str | None
    adjusted_margin: Decimal | None
    null_run: bool
    scratched: bool
    stake: Decimal | None
    raw_price: str | None
    starting_price: Decimal | None
    created_at: datetime
    updated_at: datetime


__all__ = ["RunnerCreate", "RunnerRead"]
