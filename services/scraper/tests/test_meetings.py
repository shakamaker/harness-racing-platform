"""Tests for the meeting-listing extractor against the captured listing HTML."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from harness_scraper.meetings import extract_meetings

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "services" / "parser" / "tests" / "fixtures" / "meetings"
LISTING_VIC_2024_01 = FIXTURE_DIR / "listing_vic_2024_01.html"


pytestmark = pytest.mark.skipif(
    not LISTING_VIC_2024_01.is_file(),
    reason=(
        "Live listing fixture not present. Run "
        "`python -m harness_scraper.cli fixtures --state vic --year 2024 --month 1` "
        "to capture it."
    ),
)


def test_extract_meetings_returns_known_meetings() -> None:
    html = LISTING_VIC_2024_01.read_text(encoding="utf-8")
    meetings = extract_meetings(html, state="vic")
    assert len(meetings) >= 27

    codes = {m.meeting_code for m in meetings}
    # Sentinel codes confirmed via manual inspection of the live page.
    assert "GE310124" in codes
    assert "ML300124" in codes
    assert "MX290124" in codes


def test_meeting_dates_parse_canonical_format() -> None:
    html = LISTING_VIC_2024_01.read_text(encoding="utf-8")
    meetings = extract_meetings(html, state="vic")
    geelong = next(m for m in meetings if m.meeting_code == "GE310124")
    assert geelong.track_name == "Geelong"
    assert geelong.meeting_date == date(2024, 1, 31)
    assert geelong.day_night in {"DAY", "NIGHT", "TWILIGHT"}


def test_empty_listing_returns_empty_list() -> None:
    assert extract_meetings("<html><body>no table</body></html>", state="vic") == []
