"""Lookup tables: every categorical domain value is a row, not a string.

Tables in this module are intentionally tiny (id + name/code). They exist so
that historical data is reclassifiable, joins are integer-cheap, and adding a
new race class or stewards code doesn't require a migration.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)  # ISO-ish: AU, NZ
    name: Mapped[str]
    created_at: Mapped[created_at_col]

    states: Mapped[list["State"]] = relationship(back_populates="country")


class State(Base):
    __tablename__ = "states"
    __table_args__ = (UniqueConstraint("code", "country_id", name="uq_states_code_country"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str]
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"))
    name: Mapped[str]
    created_at: Mapped[created_at_col]

    country: Mapped["Country"] = relationship(back_populates="states")


class Surface(Base):
    __tablename__ = "surfaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class TrackCondition(Base):
    __tablename__ = "track_conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class RaceGait(Base):
    __tablename__ = "race_gaits"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class StartType(Base):
    __tablename__ = "start_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class RaceClass(Base):
    __tablename__ = "race_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class AgeClass(Base):
    __tablename__ = "age_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class RaceType(Base):
    __tablename__ = "race_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class HorseSex(Base):
    __tablename__ = "horse_sexes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)  # H, M, G, F, C, R
    name: Mapped[str]


class StewardsCode(Base):
    __tablename__ = "stewards_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None] = mapped_column(default=None)


__all__ = [
    "AgeClass",
    "Country",
    "HorseSex",
    "RaceClass",
    "RaceGait",
    "RaceType",
    "StartType",
    "State",
    "StewardsCode",
    "Surface",
    "TrackCondition",
]
