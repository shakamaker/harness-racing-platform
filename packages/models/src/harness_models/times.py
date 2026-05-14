"""Race times — sectional + aggregate timings, one row per race."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
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
    gross_time_s: Mapped[Decimal | None] = mapped_column(default=None)
    lead_time_s: Mapped[Decimal | None] = mapped_column(default=None)
    mile_rate_s: Mapped[Decimal | None] = mapped_column(default=None)
    q1_s: Mapped[Decimal | None] = mapped_column(default=None)
    q2_s: Mapped[Decimal | None] = mapped_column(default=None)
    q3_s: Mapped[Decimal | None] = mapped_column(default=None)
    q4_s: Mapped[Decimal | None] = mapped_column(default=None)
    margin1: Mapped[Decimal | None] = mapped_column(default=None)
    margin2: Mapped[Decimal | None] = mapped_column(default=None)
    created_at: Mapped[created_at_col]

    race: Mapped["Race"] = relationship(back_populates="times")

    # The half-times are derived; storing them duplicates information and was
    # the source of stale-data bugs in the previous schema. The properties
    # below project them at read time.
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
