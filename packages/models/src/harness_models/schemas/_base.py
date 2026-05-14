"""Shared Pydantic v2 base + helpers for harness racing schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


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


# Constrained string types that mirror the underlying VARCHAR widths in
# sql/schema.sql. Using these in DTOs keeps the parser's contract aligned with
# what the database will actually accept.
MeetingCode = Annotated[
    str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)
]
LinkToken = Annotated[
    str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)
]


_MONEY_QUANTUM = Decimal("0.01")
_TIME_QUANTUM = Decimal("0.001")


def _to_decimal(v: object) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):  # bool is an int subclass; reject explicitly.
        raise ValueError(f"bool is not a valid Decimal source: {v!r}")
    if isinstance(v, (int, float, str)):
        return Decimal(str(v))
    raise ValueError(f"cannot convert {type(v).__name__} to Decimal")


def quantize_money(v: object) -> Decimal | None:
    """Quantise a numeric value to 2dp (currency precision). ``None`` passes through."""
    dec = _to_decimal(v)
    if dec is None:
        return None
    return dec.quantize(_MONEY_QUANTUM)


def quantize_time(v: object) -> Decimal | None:
    """Quantise a numeric value to 3dp (millisecond precision). ``None`` passes through."""
    dec = _to_decimal(v)
    if dec is None:
        return None
    return dec.quantize(_TIME_QUANTUM)


__all__ = [
    "BaseSchema",
    "LinkToken",
    "MeetingCode",
    "quantize_money",
    "quantize_time",
]
