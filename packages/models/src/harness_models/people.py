"""Persons — trainers and drivers share this table because many participants
fill both roles for different races. ``runners.trainer_id`` and
``runners.driver_id`` both FK here.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at_col


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    # link_token is the slug from harness.org.au profile URLs (the only stable
    # cross-page identifier we get for participants).
    link_token: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[created_at_col]


__all__ = ["Person"]
