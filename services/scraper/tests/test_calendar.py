"""Tests for the bulk calendar enumerator (offline)."""

from __future__ import annotations

from harness_scraper.calendar import iter_months


def test_iter_months_full_year_range() -> None:
    qs = list(iter_months("vic", year_start=1985, year_end=1986))
    assert len(qs) == 24
    assert qs[0].year == 1985 and qs[0].month == 1
    assert qs[-1].year == 1986 and qs[-1].month == 12


def test_iter_months_partial_final_year() -> None:
    qs = list(iter_months("vic", year_start=1985, year_end=2026, month_end=5))
    # 41 full years (1985..2025) + 5 months in 2026 = 41*12 + 5 = 497
    assert len(qs) == 41 * 12 + 5
    assert qs[-1].year == 2026 and qs[-1].month == 5


def test_iter_months_partial_first_year() -> None:
    qs = list(iter_months("vic", year_start=2025, year_end=2026, month_start=6, month_end=3))
    # Jun..Dec 2025 (7 months) + Jan..Mar 2026 (3 months) = 10
    assert len(qs) == 10
    assert qs[0].month == 6 and qs[0].year == 2025
    assert qs[-1].month == 3 and qs[-1].year == 2026


def test_iter_months_single_month() -> None:
    qs = list(iter_months("nsw", year_start=2024, year_end=2024, month_start=4, month_end=4))
    assert len(qs) == 1
    assert qs[0].state == "nsw" and qs[0].year == 2024 and qs[0].month == 4
