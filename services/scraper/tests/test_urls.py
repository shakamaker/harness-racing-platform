"""Tests for ``harness_scraper.urls``."""

from __future__ import annotations

import pytest

from harness_scraper.urls import (
    ALL_STATES,
    YEAR_MAX,
    YEAR_MIN,
    MonthlyResultsQuery,
    build_meeting_url,
    build_monthly_results_url,
    extract_meeting_code,
    iter_grid,
)


class TestMonthlyResultsQuery:
    def test_valid(self) -> None:
        q = MonthlyResultsQuery(month=4, year=2013, state="vic")
        assert q.month == 4

    @pytest.mark.parametrize("month", [0, 13, -1])
    def test_invalid_month(self, month: int) -> None:
        with pytest.raises(ValueError):
            MonthlyResultsQuery(month=month, year=2020, state="vic")

    @pytest.mark.parametrize("year", [YEAR_MIN - 1, YEAR_MAX + 1, 0])
    def test_invalid_year(self, year: int) -> None:
        with pytest.raises(ValueError):
            MonthlyResultsQuery(month=1, year=year, state="vic")

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError):
            MonthlyResultsQuery(month=1, year=2020, state="xyz")  # type: ignore[arg-type]


class TestBuildMonthlyResultsUrl:
    def test_matches_supplied_curl(self) -> None:
        # Mirrors docs/sample-curl.txt URL exactly.
        url = build_monthly_results_url(
            "https://www.harness.org.au",
            MonthlyResultsQuery(month=4, year=2013, state="vic"),
        )
        assert url == (
            "https://www.harness.org.au/racing/results/"
            "?month=4&year=2013&state=vic&search_type=monthly"
        )

    def test_handles_trailing_slash(self) -> None:
        url = build_monthly_results_url(
            "https://www.harness.org.au/",
            MonthlyResultsQuery(month=1, year=2024, state="nsw"),
        )
        assert "//racing" not in url


class TestBuildMeetingUrl:
    def test_absolute_path_href(self) -> None:
        url = build_meeting_url(
            "https://www.harness.org.au",
            "/racing/fields/race-fields/?mc=GE310124",
        )
        assert url == "https://www.harness.org.au/racing/fields/race-fields/?mc=GE310124"

    def test_query_only_href(self) -> None:
        url = build_meeting_url("https://www.harness.org.au", "?mc=ABC123")
        assert url.endswith("?mc=ABC123")

    def test_full_url_passthrough(self) -> None:
        full = "https://www.harness.org.au/foo/bar?mc=X"
        assert build_meeting_url("https://www.harness.org.au", full) == full


class TestExtractMeetingCode:
    def test_from_full_url(self) -> None:
        assert (
            extract_meeting_code("https://x/y?mc=GE310124&extra=1") == "GE310124"
        )

    def test_from_query_only(self) -> None:
        assert extract_meeting_code("?mc=ABC123") == "ABC123"

    def test_missing(self) -> None:
        assert extract_meeting_code("/no/query/here") is None
        assert extract_meeting_code("?other=foo") is None


class TestIterGrid:
    def test_single_state_count(self) -> None:
        grid = iter_grid(states=("vic",), year_min=2023, year_max=2024)
        assert len(grid) == 2 * 12  # two years × 12 months

    def test_default_grid_covers_all_states(self) -> None:
        grid = iter_grid(year_min=2024, year_max=2024)
        assert len(grid) == len(ALL_STATES) * 12

    def test_year_order_descending(self) -> None:
        grid = iter_grid(states=("vic",), year_min=2022, year_max=2024)
        years_seen = list(dict.fromkeys(q.year for q in grid))
        assert years_seen == [2024, 2023, 2022]
