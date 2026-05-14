"""Stewards comments — full-text + many-to-many codes per runner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, created_at_col

if TYPE_CHECKING:
    from .lookups import StewardsCode
    from .runners import Runner


class StewardsComment(Base):
    __tablename__ = "stewards_comments"

    runner_id: Mapped[int] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"), primary_key=True
    )
    full_text: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[created_at_col]

    runner: Mapped["Runner"] = relationship(back_populates="stewards_comment")
    codes: Mapped[list["StewardsCommentCode"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan"
    )


class StewardsCommentCode(Base):
    __tablename__ = "stewards_comment_codes"

    runner_id: Mapped[int] = mapped_column(
        ForeignKey("stewards_comments.runner_id", ondelete="CASCADE"),
        primary_key=True,
    )
    code_id: Mapped[int] = mapped_column(
        ForeignKey("stewards_codes.id"), primary_key=True
    )

    comment: Mapped["StewardsComment"] = relationship(back_populates="codes")
    code: Mapped["StewardsCode"] = relationship(lazy="joined")


__all__ = ["StewardsComment", "StewardsCommentCode"]
