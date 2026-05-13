"""SS:ms time conversion utilities for harness racing times.

Source-system formats observed on harness.org.au:

    "2:07:1"   ->  127.100 s   ("127:100")  -- mm:ss:tenths
    "1:58.4"   ->  118.400 s   ("118:400")  -- mm:ss.tenths
    "31.5"     ->   31.500 s   ("31:500")   -- ss.tenths
    "31"       ->   31.000 s   ("31:000")
    127.1      ->  127.100 s   ("127:100")  -- already seconds

Canonical internal representation is float seconds. The "SS:mmm" display
string is projected at the application/Pydantic boundary so we don't store
both representations and risk drift.
"""

from __future__ import annotations

from decimal import Decimal

_MAX_SECONDS = 999.999


def to_ss_ms(value: str | float | int | Decimal | None) -> tuple[str, float] | None:
    """Normalize a harness time value to ``(display, seconds)``.

    Returns ``None`` if ``value`` is ``None``. Raises ``ValueError`` on
    negative, out-of-range, or malformed input.
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
    if s < 0 or s > _MAX_SECONDS:
        raise ValueError(f"seconds out of range [0, {_MAX_SECONDS}]: {seconds!r}")
    return _format(s)


def _parse_string(text: str) -> float:
    if not text:
        raise ValueError("empty time string")
    # mm:ss:tenths (e.g. "2:07:1") or mm:ss.tenths (e.g. "1:58.4")
    if ":" in text:
        parts = text.replace(".", ":").split(":")
        if len(parts) == 2:
            sec, frac = parts
            return _combine(0, sec, frac)
        if len(parts) == 3:
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
