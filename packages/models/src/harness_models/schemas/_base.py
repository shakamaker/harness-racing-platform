"""Shared Pydantic v2 base for harness racing schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """All harness DTOs inherit ``from_attributes=True`` so they can be
    constructed directly from ORM instances via ``Model.model_validate(obj)``.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


__all__ = ["BaseSchema"]
