"""Unit tests for harness_models.time_utils.

Covers the format matrix that used to live in the module docstring:

    "2:07:1"   -> 127.100 s   ("127:100")  -- mm:ss:tenths
    "1:58.4"   -> 118.400 s   ("118:400")  -- mm:ss.tenths
    "31.5"     ->  31.500 s   ("31:500")   -- ss.tenths
    "31"       ->  31.000 s   ("31:000")
    "2:07"     -> 127.000 s   ("127:000")  -- mm:ss
    127.1      -> 127.100 s   ("127:100")  -- already seconds
"""

from __future__ import annotations

import math

import pytest

from harness_models.time_utils import format_ss_ms, to_ss_ms


class TestToSsMsHappyPath:
    def test_mm_ss_tenths(self) -> None:
        assert to_ss_ms("2:07:1") == ("127:100", 127.100)

    def test_mm_ss_with_decimal(self) -> None:
        assert to_ss_ms("1:58.4") == ("118:400", 118.400)

    def test_ss_with_decimal(self) -> None:
        assert to_ss_ms("31.5") == ("31:500", 31.500)

    def test_ss_integer_only(self) -> None:
        assert to_ss_ms("31") == ("31:000", 31.0)

    def test_mm_ss_no_fraction(self) -> None:
        # "2:07" is MM:SS — 127 whole seconds, NOT 2.07.
        assert to_ss_ms("2:07") == ("127:000", 127.0)

    def test_float_input(self) -> None:
        assert to_ss_ms(127.1) == ("127:100", 127.100)

    def test_none_returns_none(self) -> None:
        assert to_ss_ms(None) is None


class TestToSsMsErrors:
    def test_empty_string(self) -> None:
        with pytest.raises(ValueError):
            to_ss_ms("")

    def test_negative(self) -> None:
        with pytest.raises(ValueError):
            to_ss_ms(-1.0)

    def test_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            to_ss_ms(1000.0)

    def test_malformed(self) -> None:
        with pytest.raises(ValueError):
            to_ss_ms("abc:def")

    def test_bool_rejected(self) -> None:
        with pytest.raises(ValueError):
            to_ss_ms(True)  # type: ignore[arg-type]

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError):
            to_ss_ms(float("nan"))


class TestFormatSsMs:
    def test_none_passes_through(self) -> None:
        assert format_ss_ms(None) is None

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError):
            format_ss_ms(math.nan)

    def test_carry_rounding(self) -> None:
        # 99.9995 hits an IEEE-754 representation that's just under 99.9995,
        # so (frac * 1000) rounds DOWN to 999 instead of triggering the carry.
        # Lock the observed behaviour.
        assert format_ss_ms(99.9995) == "99:999"

    def test_carry_rounding_explicit(self) -> None:
        # 99.9999 unambiguously triggers the ms==1000 carry branch.
        assert format_ss_ms(99.9999) == "100:000"
