"""Race-time DTOs. Display strings are projected, not stored."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import computed_field

from ..time_utils import format_ss_ms
from ._base import BaseSchema


class RaceTimeCreate(BaseSchema):
    race_id: int
    gross_time_s: Decimal | None = None
    lead_time_s: Decimal | None = None
    mile_rate_s: Decimal | None = None
    q1_s: Decimal | None = None
    q2_s: Decimal | None = None
    q3_s: Decimal | None = None
    q4_s: Decimal | None = None
    margin1: Decimal | None = None
    margin2: Decimal | None = None


class RaceTimeRead(BaseSchema):
    race_id: int
    gross_time_s: Decimal | None
    lead_time_s: Decimal | None
    mile_rate_s: Decimal | None
    q1_s: Decimal | None
    q2_s: Decimal | None
    q3_s: Decimal | None
    q4_s: Decimal | None
    margin1: Decimal | None
    margin2: Decimal | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gross_time_display(self) -> str | None:
        return format_ss_ms(self.gross_time_s)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def lead_time_display(self) -> str | None:
        return format_ss_ms(self.lead_time_s)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mile_rate_display(self) -> str | None:
        return format_ss_ms(self.mile_rate_s)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_half_s(self) -> Decimal | None:
        if self.q1_s is None or self.q2_s is None:
            return None
        return self.q1_s + self.q2_s

    @computed_field  # type: ignore[prop-decorator]
    @property
    def second_half_s(self) -> Decimal | None:
        if self.q3_s is None or self.q4_s is None:
            return None
        return self.q3_s + self.q4_s


__all__ = ["RaceTimeCreate", "RaceTimeRead"]
