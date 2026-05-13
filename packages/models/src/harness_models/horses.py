"""Horses — keyed by the source-system id from harness.org.au."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col, updated_at_col

if TYPE_CHECKING:
    from .lookups import HorseSex
    from .runners import Runner


class Horse(Base):
    __tablename__ = "horses"

    # horse_id is NOT autoincrement — it's the upstream id used as the
    # cross-meeting key for form lookups. Insertions must supply it.
    horse_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    horse_name: Mapped[str] = mapped_column(index=True)
    sex_id: Mapped[int | None] = mapped_column(ForeignKey("horse_sexes.id"), default=None)
    foaled: Mapped[int | None] = mapped_column(default=None)
    sire_id: Mapped[int | None] = mapped_column(ForeignKey("horses.horse_id"), default=None)
    dam_id: Mapped[int | None] = mapped_column(ForeignKey("horses.horse_id"), default=None)
    created_at: Mapped[created_at_col]
    updated_at: Mapped[updated_at_col]

    sex: Mapped["HorseSex | None"] = relationship(lazy="joined")
    sire: Mapped["Horse | None"] = relationship(
        remote_side="Horse.horse_id", foreign_keys=[sire_id], post_update=True
    )
    dam: Mapped["Horse | None"] = relationship(
        remote_side="Horse.horse_id", foreign_keys=[dam_id], post_update=True
    )
    runners: Mapped[list["Runner"]] = relationship(back_populates="horse")


__all__ = ["Horse"]
