"""Extract meeting rows from the monthly results listing (CLAUDE.md §4.1.3).

This is scraper-owned (not parser-owned) because the listing page is what the
scraper iterates to enqueue downloads. The parser owns race-result HTML only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Final

from selectolax.parser import HTMLParser

from harness_scraper.logging_setup import get_logger
from harness_scraper.urls import State, extract_meeting_code

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MeetingRow:
    """One parsed row from ``table.meetingListFull``."""

    meeting_code: str
    track_name: str
    state: State
    meeting_date: date
    day_night: str  # 'DAY' | 'NIGHT' | 'TWILIGHT' | 'UNKNOWN'
    meeting_href: str


_DATE_PATTERNS: Final[tuple[str, ...]] = (
    "%d/%m/%Y",  # 01/04/2013
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d %B %Y",  # 1 April 2013
    "%d %b %Y",  # 1 Apr 2013
    "%a, %d %B %Y",  # Wed, 24 January 2024
    "%a, %d %b %Y",  # Wed, 24 Jan 2024 ← canonical harness.org.au format
    "%A, %d %B %Y",  # Wednesday, 24 January 2024
    "%A, %d %b %Y",
)


def _parse_date(text: str) -> date | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    from datetime import datetime

    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _infer_day_night(text: str) -> str:
    lowered = text.lower()
    if "twilight" in lowered:
        return "TWILIGHT"
    if "night" in lowered:
        return "NIGHT"
    if "day" in lowered:
        return "DAY"
    return "UNKNOWN"


_TRACK_CLEAN_RE: Final = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    if text is None:
        return ""
    return _TRACK_CLEAN_RE.sub(" ", text).strip()


def extract_meetings(html: str, *, state: State) -> list[MeetingRow]:
    """Parse ``<table class="meetingListFull">`` into ``MeetingRow`` records.

    Returns an empty list (rather than raising) if the table is missing — the
    monthly listing for some (state, year, month) tuples legitimately has no
    meetings and we should record that as zero rows, not an error.
    """
    tree = HTMLParser(html)
    tables = tree.css("table.meetingListFull")
    if not tables:
        log.warning("no_meeting_table", state=state, html_bytes=len(html))
        return []

    rows: list[MeetingRow] = []
    seen_codes: set[str] = set()
    trs = [tr for table in tables for tr in table.css("tr")]
    for tr in trs:
        # The header row uses <th>; skip anything without an anchor.
        anchor = tr.css_first("a[href*='mc=']")
        if anchor is None:
            continue

        href = anchor.attributes.get("href", "")
        if not href:
            continue
        meeting_code = extract_meeting_code(href)
        if not meeting_code:
            log.warning("meeting_no_code", href=href, state=state)
            continue

        track_name = _clean(anchor.text())

        # Date and day/night cells are positional in the harness.org.au markup.
        # We collect all cells, find the first that parses as a date, and use
        # the textual content of remaining cells to classify day_night.
        cells = [_clean(td.text()) for td in tr.css("td")]
        meeting_date: date | None = None
        day_night = "UNKNOWN"
        for c in cells:
            if meeting_date is None:
                meeting_date = _parse_date(c)
            day_night_guess = _infer_day_night(c)
            if day_night_guess != "UNKNOWN":
                day_night = day_night_guess

        if meeting_date is None:
            log.warning(
                "meeting_no_date",
                meeting_code=meeting_code,
                track=track_name,
                cells=cells,
                state=state,
            )
            continue

        if meeting_code in seen_codes:
            continue
        seen_codes.add(meeting_code)
        rows.append(
            MeetingRow(
                meeting_code=meeting_code,
                track_name=track_name,
                state=state,
                meeting_date=meeting_date,
                day_night=day_night,
                meeting_href=href,
            )
        )

    log.info("meetings_extracted", state=state, count=len(rows))
    return rows
