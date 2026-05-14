"""Runners — one horse's entry in one race."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col, updated_at_col

if TYPE_CHECKING:
    from .horses import Horse
    from .people import Person
    from .races import Race
    from .stewards import StewardsComment


class Runner(Base):
    __tablename__ = "runners"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_id", name="uq_runners_race_horse"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="RESTRICT"))
    horse_id: Mapped[int] = mapped_column(
        ForeignKey("horses.horse_id", ondelete="RESTRICT")
    )
    runner_number: Mapped[int | None] = mapped_column(default=None)
    barrier: Mapped[int | None] = mapped_column(default=None)
    barrier_raw: Mapped[str | None] = mapped_column(String(8), default=None)
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), default=None)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), default=None)
    finish_position: Mapped[int | None] = mapped_column(default=None)
    raw_margin: Mapped[str | None] = mapped_column(String(32), default=None)
    adjusted_margin: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), default=None)
    null_run: Mapped[bool] = mapped_column(default=False)
    scratched: Mapped[bool] = mapped_column(default=False)
    stake: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    raw_price: Mapped[str | None] = mapped_column(String(32), default=None)
    starting_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), default=None)
    created_at: Mapped[created_at_col]
    updated_at: Mapped[updated_at_col]

    race: Mapped["Race"] = relationship(back_populates="runners")
    horse: Mapped["Horse"] = relationship(back_populates="runners", lazy="joined")
    trainer: Mapped["Person | None"] = relationship(
        foreign_keys=[trainer_id], lazy="joined"
    )
    driver: Mapped["Person | None"] = relationship(
        foreign_keys=[driver_id], lazy="joined"
    )
    stewards_comment: Mapped["StewardsComment | None"] = relationship(
        back_populates="runner", uselist=False, cascade="all, delete-orphan"
    )


__all__ = ["Runner"]
