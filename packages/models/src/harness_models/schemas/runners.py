"""Runner DTOs."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from pydantic import field_validator, model_validator

from ._base import BaseSchema, quantize_money, quantize_time


_BARRIER_LEADING_INT = re.compile(r"^[A-Za-z]*(\d+)")


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

    @field_validator("stake", "starting_price", mode="before")
    @classmethod
    def _quantise_money(cls, v: object) -> Decimal | None:
        return quantize_money(v)

    @field_validator("adjusted_margin", mode="before")
    @classmethod
    def _quantise_time(cls, v: object) -> Decimal | None:
        return quantize_time(v)

    @model_validator(mode="after")
    def _barrier_consistency(self) -> "RunnerCreate":
        if self.barrier is not None and self.barrier_raw is not None:
            m = _BARRIER_LEADING_INT.match(self.barrier_raw)
            if m is None:
                raise ValueError(
                    f"barrier_raw={self.barrier_raw!r} has no leading integer "
                    f"but barrier={self.barrier} was supplied"
                )
            extracted = int(m.group(1))
            if extracted != self.barrier:
                raise ValueError(
                    f"barrier ({self.barrier}) disagrees with leading integer of "
                    f"barrier_raw ({self.barrier_raw!r} -> {extracted})"
                )
        return self


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
