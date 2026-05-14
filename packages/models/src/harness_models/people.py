"""Persons — trainers and drivers share this table because many participants
fill both roles for different races. ``runners.trainer_id`` and
``runners.driver_id`` both FK here.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at_col


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    link_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[created_at_col]


__all__ = ["Person"]
