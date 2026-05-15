"""Bulk calendar enumeration across (state, year, month) tuples.

Iterates the monthly listing grid (CLAUDE.md §4.1.1), persists each listing's
raw HTML, parses meeting rows via :func:`extract_meetings`, and emits a
per-year JSON manifest aggregating all rows.

The runner is resumable: a month is skipped if its listing HTML already
exists on disk *and* its meeting rows are present in the year manifest. To
force a re-fetch, pass ``--refresh`` or delete the listing HTML.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from harness_scraper.browser import HarnessBrowser
from harness_scraper.fetcher import fetch_monthly_listing
from harness_scraper.logging_setup import get_logger
from harness_scraper.meetings import MeetingRow, extract_meetings
from harness_scraper.rate_limit import TokenBucket
from harness_scraper.settings import ScraperSettings
from harness_scraper.urls import (
    MonthlyResultsQuery,
    State,
    build_monthly_results_url,
)

log = get_logger(__name__)


def _listing_html_path(base: Path, state: State, year: int, month: int) -> Path:
    return base / "listings" / state / str(year) / f"{month:02d}.html"


def _year_manifest_path(base: Path, state: State, year: int) -> Path:
    return base / "calendar" / state / f"{year}.json"


def _row_to_dict(row: MeetingRow) -> dict:
    d = asdict(row)
    d["meeting_date"] = row.meeting_date.isoformat()
    return d


def iter_months(
    state: State,
    *,
    year_start: int,
    year_end: int,
    month_start: int = 1,
    month_end: int = 12,
) -> Iterable[MonthlyResultsQuery]:
    """Yield queries from (year_start, 1) through (year_end, month_end) inclusive.

    Iterates chronologically (oldest first). For the final year only months
    1..month_end are yielded; for the first year only month_start..12.
    """
    for year in range(year_start, year_end + 1):
        m_lo = month_start if year == year_start else 1
        m_hi = month_end if year == year_end else 12
        for month in range(m_lo, m_hi + 1):
            yield MonthlyResultsQuery(month=month, year=year, state=state)


async def run_calendar(
    *,
    state: State,
    year_start: int,
    year_end: int,
    month_start: int,
    month_end: int,
    settings: ScraperSettings,
    raw_dir: Path,
    data_dir: Path,
    refresh: bool = False,
) -> dict:
    """Enumerate the monthly listing grid for one state and persist results.

    Returns a summary dict with per-year counts and the total meetings ingested.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    rate_limiter = TokenBucket(rate_per_minute=settings.rate_limit_rpm)
    queries = list(
        iter_months(
            state,
            year_start=year_start,
            year_end=year_end,
            month_start=month_start,
            month_end=month_end,
        )
    )

    # Group queries by year so we can flush a manifest per year.
    by_year: dict[int, list[MonthlyResultsQuery]] = {}
    for q in queries:
        by_year.setdefault(q.year, []).append(q)

    totals: dict[int, int] = {}
    grand_total = 0
    months_fetched = 0
    months_skipped = 0

    async with HarnessBrowser(settings, session_id=f"calendar-{state}") as browser:
        previous_url: str | None = None

        for year in sorted(by_year):
            year_rows: list[MeetingRow] = []
            manifest_path = _year_manifest_path(data_dir, state, year)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)

            for q in by_year[year]:
                html_path = _listing_html_path(raw_dir, state, q.year, q.month)
                html_path.parent.mkdir(parents=True, exist_ok=True)

                if html_path.exists() and not refresh:
                    html = html_path.read_text(encoding="utf-8")
                    months_skipped += 1
                    log.info(
                        "calendar_skip_cached",
                        state=state,
                        year=q.year,
                        month=q.month,
                        path=str(html_path),
                    )
                else:
                    referer = previous_url
                    result = await fetch_monthly_listing(
                        browser, q, settings=settings, rate_limiter=rate_limiter, referer=referer
                    )
                    html = result.html
                    html_path.write_text(html, encoding="utf-8")
                    previous_url = build_monthly_results_url(settings.base_url, q)
                    months_fetched += 1
                    log.info(
                        "calendar_listing_saved",
                        state=state,
                        year=q.year,
                        month=q.month,
                        bytes=len(html),
                        path=str(html_path),
                    )

                rows = extract_meetings(html, state=state)
                year_rows.extend(rows)
                log.info(
                    "calendar_month_done",
                    state=state,
                    year=q.year,
                    month=q.month,
                    meetings=len(rows),
                )

            # Deduplicate by meeting_code (same code shouldn't appear twice in
            # one calendar year, but defensive against listing quirks).
            seen: set[str] = set()
            deduped: list[MeetingRow] = []
            for row in year_rows:
                if row.meeting_code in seen:
                    continue
                seen.add(row.meeting_code)
                deduped.append(row)

            manifest_path.write_text(
                json.dumps([_row_to_dict(r) for r in deduped], indent=2, sort_keys=True),
                encoding="utf-8",
            )
            totals[year] = len(deduped)
            grand_total += len(deduped)
            log.info(
                "calendar_year_manifest_written",
                state=state,
                year=year,
                meetings=len(deduped),
                path=str(manifest_path),
            )

    summary = {
        "state": state,
        "year_start": year_start,
        "year_end": year_end,
        "month_start": month_start,
        "month_end": month_end,
        "months_fetched": months_fetched,
        "months_skipped": months_skipped,
        "total_meetings": grand_total,
        "per_year_counts": dict(sorted(totals.items())),
    }
    summary_path = data_dir / "calendar" / state / "_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("calendar_run_complete", **{k: v for k, v in summary.items() if k != "per_year_counts"})
    return summary
