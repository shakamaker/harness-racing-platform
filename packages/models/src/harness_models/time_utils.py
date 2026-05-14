"""Normalize harness times to (display_str, seconds_float)."""

from __future__ import annotations

import math
from decimal import Decimal

_MAX_SECONDS = 999.999


def to_ss_ms(value: str | float | int | Decimal | None) -> tuple[str, float] | None:
    """Normalize a harness time value to ``(display, seconds)``.

    Returns ``None`` if ``value`` is ``None``. Raises ``ValueError`` on
    negative, out-of-range, NaN, or malformed input.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly.
        raise ValueError(f"bool is not a valid time value: {value!r}")
    if isinstance(value, (int, float, Decimal)):
        seconds = float(value)
    elif isinstance(value, str):
        seconds = _parse_string(value.strip())
    else:
        raise ValueError(f"unsupported time type: {type(value).__name__}")
    if math.isnan(seconds):
        raise ValueError(f"NaN is not a valid time value: {value!r}")
    if seconds < 0:
        raise ValueError(f"negative time not allowed: {value!r}")
    if seconds > _MAX_SECONDS:
        raise ValueError(f"time exceeds {_MAX_SECONDS}s: {value!r}")
    return _format(seconds), round(seconds, 3)


def format_ss_ms(seconds: float | Decimal | None) -> str | None:
    """Project a seconds value to ``"SS:mmm"`` display form. ``None`` passes through."""
    if seconds is None:
        return None
    s = float(seconds)
    if math.isnan(s):
        raise ValueError(f"NaN is not a valid time value: {seconds!r}")
    if s < 0 or s > _MAX_SECONDS:
        raise ValueError(f"seconds out of range [0, {_MAX_SECONDS}]: {seconds!r}")
    return _format(s)


def _parse_string(text: str) -> float:
    if not text:
        raise ValueError("empty time string")
    if ":" in text:
        if "." in text:
            # "M:SS.t" / "M:SS.tt" — minutes:seconds with decimal fraction.
            parts = text.replace(".", ":").split(":")
            if len(parts) == 3:
                mins, sec, frac = parts
                return _combine(mins, sec, frac)
            raise ValueError(f"malformed time string: {text!r}")
        parts = text.split(":")
        if len(parts) == 2:
            # "M:SS" — minutes : whole seconds (per harness convention).
            mins, sec = parts
            return _combine(mins, sec, "")
        if len(parts) == 3:
            # "M:SS:tenths" — colon-separated triple.
            mins, sec, frac = parts
            return _combine(mins, sec, frac)
        raise ValueError(f"malformed time string: {text!r}")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"malformed time string: {text!r}") from exc


def _combine(mins: str | int, sec: str, frac: str) -> float:
    try:
        m = int(mins) if mins != "" else 0
        s = int(sec)
        # tenths/hundredths/thousandths — pad-right so "1" -> 100ms, "12" -> 120ms.
        f_ms = int(frac.ljust(3, "0")[:3]) if frac else 0
    except ValueError as exc:
        raise ValueError(f"malformed time components: {mins}:{sec}:{frac}") from exc
    return m * 60 + s + f_ms / 1000.0


def _format(seconds: float) -> str:
    whole = int(seconds)
    ms = int(round((seconds - whole) * 1000))
    if ms == 1000:  # carry from rounding 999.9995 etc.
        whole += 1
        ms = 0
    return f"{whole}:{ms:03d}"
