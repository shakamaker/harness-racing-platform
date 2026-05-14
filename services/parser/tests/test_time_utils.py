"""Tests for time_utils.to_ss_ms (CLAUDE.md §4.2.3)."""

from __future__ import annotations

import math

import pytest

from harness_parser.time_utils import TimeParseError, format_ss_ms, to_ss_ms


class TestColonTripleForm:
    """``M:SS:t`` is the canonical harness.org.au form."""

    def test_spec_example_gross_time(self) -> None:
        display, secs = to_ss_ms("2:07:1")
        assert display == "127:100"
        assert math.isclose(secs, 127.1, abs_tol=1e-9)

    def test_spec_example_mile_rate(self) -> None:
        display, secs = to_ss_ms("1:58:9")
        assert display == "118:900"
        assert math.isclose(secs, 118.9, abs_tol=1e-9)

    def test_two_digit_fraction_treated_as_hundredths(self) -> None:
        display, secs = to_ss_ms("2:07:15")
        assert math.isclose(secs, 127.150, abs_tol=1e-9)
        assert display == "127:150"

    def test_three_digit_fraction_treated_as_milliseconds(self) -> None:
        display, secs = to_ss_ms("1:00:123")
        assert math.isclose(secs, 60.123, abs_tol=1e-9)
        assert display == "60:123"

    def test_zero_minute_pad(self) -> None:
        display, _ = to_ss_ms("0:30:5")
        assert display == "30:500"


class TestColonDecimalForm:
    """``M:SS.t`` form sometimes used for mile-rate display."""

    def test_mile_rate_with_dot(self) -> None:
        display, secs = to_ss_ms("1:58.9")
        assert display == "118:900"
        assert math.isclose(secs, 118.9, abs_tol=1e-9)


class TestColonWholeForm:
    """``M:SS`` (no fractional component)."""

    def test_whole_minutes_and_seconds(self) -> None:
        display, secs = to_ss_ms("2:07")
        assert display == "127:000"
        assert secs == 127.0


class TestBareSeconds:
    """Quarters / lead-times often come through as bare seconds."""

    def test_quarter_split(self) -> None:
        assert to_ss_ms("31.5") == ("31:500", 31.5)

    def test_lead_time_short(self) -> None:
        assert to_ss_ms("7.4") == ("7:400", 7.4)

    def test_integer_seconds(self) -> None:
        assert to_ss_ms("60") == ("60:000", 60.0)

    def test_three_digit_decimal(self) -> None:
        display, secs = to_ss_ms("31.500")
        assert display == "31:500"
        assert math.isclose(secs, 31.5, abs_tol=1e-9)


class TestNumericInput:
    """Numeric inputs round-trip through the same display formatter."""

    def test_float_input(self) -> None:
        assert to_ss_ms(7.4) == ("7:400", 7.4)

    def test_int_input(self) -> None:
        assert to_ss_ms(60) == ("60:000", 60.0)

    def test_float_with_fp_noise_rounds_correctly(self) -> None:
        # 127.0999999... is what 2*60 + 7 + 0.1 produces in float arithmetic.
        # The display must round, not truncate.
        display, _ = to_ss_ms(127.0 + 0.1 - 1e-12)
        assert display == "127:100"


class TestWhitespaceAndTolerance:
    def test_strips_surrounding_whitespace(self) -> None:
        assert to_ss_ms("  2:07:1  ") == ("127:100", 127.1)

    def test_strips_trailing_s_unit(self) -> None:
        assert to_ss_ms("31.5s") == ("31:500", 31.5)


class TestErrors:
    @pytest.mark.parametrize(
        "value",
        ["", "   ", "n/a", "DNF", "scratched", "2:07:1:5", "abc", ":", "::"],
    )
    def test_unparseable_raises(self, value: str) -> None:
        with pytest.raises(TimeParseError):
            to_ss_ms(value)

    def test_negative_seconds_rejected(self) -> None:
        with pytest.raises(TimeParseError):
            to_ss_ms(-1.5)

    def test_nan_rejected(self) -> None:
        with pytest.raises(TimeParseError):
            to_ss_ms(float("nan"))

    def test_unsupported_type_rejected(self) -> None:
        with pytest.raises(TimeParseError):
            to_ss_ms(None)  # type: ignore[arg-type]


class TestFormatSsMs:
    """``format_ss_ms`` is the lower-level renderer used by other modules."""

    def test_basic(self) -> None:
        assert format_ss_ms(127.1) == "127:100"

    def test_pad_three_digits(self) -> None:
        assert format_ss_ms(60.005) == "60:005"

    def test_round_up(self) -> None:
        assert format_ss_ms(60.0009) == "60:001"

    def test_zero(self) -> None:
        assert format_ss_ms(0.0) == "0:000"
