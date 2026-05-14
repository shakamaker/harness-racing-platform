"""Race times — sectional + aggregate timings, one row per race."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col
from .time_utils import format_ss_ms

if TYPE_CHECKING:
    from .races import Race


class RaceTime(Base):
    __tablename__ = "race_times"

    race_id: Mapped[int] = mapped_column(
        ForeignKey("races.id", ondelete="CASCADE"), primary_key=True
    )
    gross_time_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    lead_time_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    mile_rate_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    q1_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    q2_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    q3_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    q4_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), default=None)
    margin1: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), default=None)
    margin2: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), default=None)
    created_at: Mapped[created_at_col]

    race: Mapped["Race"] = relationship(back_populates="times")

    # Derived from q1..q4 at read time; never stored.
    @property
    def first_half_s(self) -> Decimal | None:
        return _sum_or_none(self.q1_s, self.q2_s)

    @property
    def last_half_s(self) -> Decimal | None:
        return _sum_or_none(self.q3_s, self.q4_s)

    @property
    def gross_time_display(self) -> str | None:
        return format_ss_ms(self.gross_time_s)

    @property
    def lead_time_display(self) -> str | None:
        return format_ss_ms(self.lead_time_s)

    @property
    def mile_rate_display(self) -> str | None:
        return format_ss_ms(self.mile_rate_s)


def _sum_or_none(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None:
        return None
    return a + b


__all__ = ["RaceTime"]
