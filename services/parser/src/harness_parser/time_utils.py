"""Race-time normalisation utilities (CLAUDE.md §4.2.3).

Canonical display form is ``"<int_seconds>:<3-digit-ms>"`` (e.g. ``"127:100"``).
Canonical numeric form is total seconds as ``float``.

Supported inputs:

* ``"M:SS:t"``      — minutes : seconds : tenths-of-second (most common on
  harness.org.au, e.g. ``"2:07:1"`` → 127.100s, ``"1:58:9"`` → 118.900s).
* ``"M:SS:tt"``     — minutes : seconds : hundredths (rare, but tolerated).
* ``"M:SS.t"``      — minutes : seconds . fractional (e.g. ``"1:58.9"``).
* ``"M:SS"``        — minutes : whole-seconds.
* ``"SS.t"`` / ``"SS.tt"`` / ``"SS.ttt"`` — bare seconds with decimal fraction
  (quarters and lead times come through this way, e.g. ``"7.4"``, ``"31.5"``).
* ``"SS"``          — bare integer seconds.
* ``float`` / ``int`` — already in seconds.

Whitespace is stripped. Empty / ``None`` / unparseable input raises ``ValueError``
so the caller can route into ``parse_dlq``.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["to_ss_ms", "format_ss_ms", "TimeParseError"]


class TimeParseError(ValueError):
    """Raised when a time string cannot be parsed into seconds."""


# Match "M:SS:t" / "M:SS:tt" / "M:SS:ttt"  — colon-separated triple where the
# tail digits are a fractional-second indicator. We support 1-3 trailing digits;
# the harness.org.au convention is 1 digit (tenths) but we accept tighter
# precision so the parser stays robust.
_COLON_TRIPLE: Final = re.compile(r"^(\d{1,3}):(\d{1,2}):(\d{1,3})$")

# "M:SS.t"  / "M:SS.tt" — minutes:seconds with decimal fraction.
_COLON_DECIMAL: Final = re.compile(r"^(\d{1,3}):(\d{1,2})\.(\d{1,3})$")

# "M:SS" — minutes : whole seconds (no fraction).
_COLON_WHOLE: Final = re.compile(r"^(\d{1,3}):(\d{1,2})$")

# Bare seconds with optional decimal: "31.5", "7.4", "127", "127.123".
_BARE_SECONDS: Final = re.compile(r"^(\d{1,5})(?:\.(\d{1,3}))?$")


def to_ss_ms(value: str | float | int) -> tuple[str, float]:
    """Normalise a harness-racing time into ``(display, seconds)``.

    >>> to_ss_ms("2:07:1")
    ('127:100', 127.1)
    >>> to_ss_ms("1:58:9")
    ('118:900', 118.9)
    >>> to_ss_ms("31.5")
    ('31:500', 31.5)
    >>> to_ss_ms(7.4)
    ('7:400', 7.4)
    """
    seconds = _parse_to_seconds(value)
    return format_ss_ms(seconds), seconds


def format_ss_ms(seconds: float) -> str:
    """Render total seconds as canonical ``"SS:mmm"``.

    Negative inputs are an error — race times are non-negative.
    """
    if seconds < 0:
        raise TimeParseError(f"negative time not valid for race data: {seconds!r}")
    # Round to the nearest millisecond before splitting so FP noise like
    # 127.0999999 doesn't display as "126:999".
    total_ms = round(seconds * 1000)
    whole = total_ms // 1000
    millis = total_ms % 1000
    return f"{whole}:{millis:03d}"


def _parse_to_seconds(value: str | float | int) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value != value:  # NaN guard
            raise TimeParseError("cannot normalise NaN")
        return float(value)

    if not isinstance(value, str):
        raise TimeParseError(f"unsupported type for time value: {type(value).__name__}")

    cleaned = value.strip()
    if not cleaned:
        raise TimeParseError("empty time string")

    # Harness pages occasionally render times with a trailing 's' or stray
    # whitespace between tokens; tolerate both.
    cleaned = cleaned.rstrip("sS").strip()

    if m := _COLON_TRIPLE.match(cleaned):
        minutes, secs, frac = m.groups()
        return _combine(int(minutes), int(secs), frac)

    if m := _COLON_DECIMAL.match(cleaned):
        minutes, secs, frac = m.groups()
        return _combine(int(minutes), int(secs), frac)

    if m := _COLON_WHOLE.match(cleaned):
        minutes, secs = m.groups()
        return int(minutes) * 60 + int(secs)

    if m := _BARE_SECONDS.match(cleaned):
        secs, frac = m.groups()
        whole = int(secs)
        if frac is None:
            return float(whole)
        return whole + _fraction_to_seconds(frac)

    raise TimeParseError(f"unrecognised time format: {value!r}")


def _combine(minutes: int, seconds: int, frac_digits: str) -> float:
    return minutes * 60 + seconds + _fraction_to_seconds(frac_digits)


def _fraction_to_seconds(frac_digits: str) -> float:
    """Convert a 1-3 digit fractional string into a sub-second float.

    ``"1"`` → 0.100 (one tenth), ``"15"`` → 0.150, ``"123"`` → 0.123.
    """
    if not frac_digits:
        return 0.0
    digits = frac_digits[:3]
    scale = 10 ** (3 - len(digits))
    return int(digits) * scale / 1000.0
