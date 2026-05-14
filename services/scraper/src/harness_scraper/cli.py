"""Scraper CLI entry points.

Usage::

    # Fetch one monthly listing + N meeting HTMLs for fixtures
    python -m harness_scraper.cli fixtures --state vic --year 2024 --month 1 --limit 3

    # Fetch a single meeting by code
    python -m harness_scraper.cli meeting --state vic --year 2024 --code <mc>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import cast

from harness_scraper.browser import HarnessBrowser
from harness_scraper.calendar import run_calendar
from harness_scraper.fetcher import fetch_meeting_html, fetch_monthly_listing
from harness_scraper.meetings_download import run_meeting_downloads
from harness_scraper.logging_setup import configure_logging, get_logger
from harness_scraper.meetings import extract_meetings
from harness_scraper.rate_limit import TokenBucket
from harness_scraper.settings import ScraperSettings, get_settings
from harness_scraper.urls import (
    ALL_STATES,
    YEAR_MAX,
    YEAR_MIN,
    MonthlyResultsQuery,
    State,
    build_monthly_results_url,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness-scraper")
    sub = p.add_subparsers(dest="cmd", required=True)

    fx = sub.add_parser("fixtures", help="Fetch a listing + N meeting HTMLs into fixtures dir")
    fx.add_argument("--state", required=True, choices=ALL_STATES)
    fx.add_argument("--year", type=int, required=True)
    fx.add_argument("--month", type=int, required=True)
    fx.add_argument("--limit", type=int, default=3, help="max meetings to download")
    fx.add_argument(
        "--out-dir",
        type=Path,
        default=Path("services/parser/tests/fixtures/meetings"),
        help="Where to drop listing + per-meeting HTML files (defaults to parser fixtures dir).",
    )

    mt = sub.add_parser("meeting", help="Fetch a single meeting page by code")
    mt.add_argument("--state", required=True, choices=ALL_STATES)
    mt.add_argument("--year", type=int, required=True)
    mt.add_argument("--code", required=True, help="meeting_code (the ?mc= value)")

    li = sub.add_parser("listing", help="Fetch a single monthly listing page")
    li.add_argument("--state", required=True, choices=ALL_STATES)
    li.add_argument("--year", type=int, required=True)
    li.add_argument("--month", type=int, required=True)

    cal = sub.add_parser(
        "calendar",
        help="Enumerate monthly listings across a year range for one state (resumable).",
    )
    cal.add_argument("--state", required=True, choices=ALL_STATES)
    cal.add_argument("--year-start", type=int, default=YEAR_MIN)
    cal.add_argument("--year-end", type=int, default=YEAR_MAX)
    cal.add_argument("--month-start", type=int, default=1, help="First month in year-start (1-12)")
    cal.add_argument("--month-end", type=int, default=12, help="Last month in year-end (1-12)")
    cal.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("./raw_html"),
        help="Directory for raw listing HTML (default ./raw_html, listings live under listings/{state}/{year}/{mm}.html).",
    )
    cal.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="Directory for per-year manifests (default ./data, manifests live under calendar/{state}/{year}.json).",
    )
    cal.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch every listing even if cached HTML already exists.",
    )

    md = sub.add_parser(
        "meetings-download",
        help=(
            "Concurrent per-meeting HTML download driven by calendar year manifests "
            "(CLAUDE.md §4.1.4). Resumable."
        ),
    )
    md.add_argument("--state", required=True, choices=ALL_STATES)
    md.add_argument("--year-start", type=int, required=True)
    md.add_argument("--year-end", type=int, required=True)
    md.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Concurrent worker count (default: SCRAPER_WORKERS_PER_STATE).",
    )
    md.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("./raw_html"),
    )
    md.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
    )
    md.add_argument(
        "--watch",
        action="store_true",
        help=(
            "Long-running mode: re-scan manifests periodically and pick up new "
            "meetings as the calendar runner publishes them. Exits after "
            "several idle passes with no new work."
        ),
    )
    md.add_argument(
        "--poll-seconds",
        type=float,
        default=30.0,
        help="Seconds between manifest re-scans in watch mode.",
    )
    return p


async def _cmd_fixtures(args: argparse.Namespace, settings: ScraperSettings) -> int:
    log = get_logger("cli.fixtures")
    state = cast(State, args.state)
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rate_limiter = TokenBucket(rate_per_minute=settings.rate_limit_rpm)
    async with HarnessBrowser(settings, session_id=f"fixtures-{state}") as browser:
        query = MonthlyResultsQuery(month=args.month, year=args.year, state=state)
        listing = await fetch_monthly_listing(
            browser, query, settings=settings, rate_limiter=rate_limiter
        )
        listing_path = out_dir / f"listing_{state}_{args.year}_{args.month:02d}.html"
        listing_path.write_text(listing.html, encoding="utf-8")
        log.info("listing_saved", path=str(listing_path), bytes=len(listing.html))

        meetings = extract_meetings(listing.html, state=state)
        log.info("listing_parsed", count=len(meetings))

        manifest: list[dict] = []
        for row in meetings[: args.limit]:
            result, html_path = await fetch_meeting_html(
                browser,
                meeting_code=row.meeting_code,
                meeting_href=row.meeting_href,
                state=state,
                year=args.year,
                settings=settings,
                rate_limiter=rate_limiter,
                referer=build_monthly_results_url(settings.base_url, query),
            )
            # Also drop a copy under the fixtures dir for parser tests.
            fixture_copy = out_dir / f"meeting_{state}_{row.meeting_code}.html"
            fixture_copy.write_text(result.html, encoding="utf-8")
            manifest.append(
                {
                    "meeting_code": row.meeting_code,
                    "track_name": row.track_name,
                    "state": row.state,
                    "meeting_date": row.meeting_date.isoformat(),
                    "day_night": row.day_night,
                    "meeting_href": row.meeting_href,
                    "html_path": str(html_path),
                    "fixture_path": str(fixture_copy),
                    "bytes": len(result.html),
                }
            )

        manifest_path = out_dir / f"manifest_{state}_{args.year}_{args.month:02d}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        log.info("manifest_written", path=str(manifest_path), count=len(manifest))
    return 0


async def _cmd_meeting(args: argparse.Namespace, settings: ScraperSettings) -> int:
    state = cast(State, args.state)
    rate_limiter = TokenBucket(rate_per_minute=settings.rate_limit_rpm)
    async with HarnessBrowser(settings, session_id=f"meeting-{state}") as browser:
        result, html_path = await fetch_meeting_html(
            browser,
            meeting_code=args.code,
            meeting_href=f"?mc={args.code}",
            state=state,
            year=args.year,
            settings=settings,
            rate_limiter=rate_limiter,
        )
        get_logger("cli.meeting").info(
            "saved", path=str(html_path), status=result.status, bytes=len(result.html)
        )
    return 0


async def _cmd_listing(args: argparse.Namespace, settings: ScraperSettings) -> int:
    state = cast(State, args.state)
    rate_limiter = TokenBucket(rate_per_minute=settings.rate_limit_rpm)
    async with HarnessBrowser(settings, session_id=f"listing-{state}") as browser:
        query = MonthlyResultsQuery(month=args.month, year=args.year, state=state)
        listing = await fetch_monthly_listing(
            browser, query, settings=settings, rate_limiter=rate_limiter
        )
        meetings = extract_meetings(listing.html, state=state)
        for m in meetings:
            print(
                f"{m.meeting_code}\t{m.meeting_date.isoformat()}\t"
                f"{m.day_night}\t{m.track_name}\t{m.meeting_href}"
            )
    return 0


async def _cmd_meetings_download(args: argparse.Namespace, settings: ScraperSettings) -> int:
    state = cast(State, args.state)
    counters = await run_meeting_downloads(
        state=state,
        year_start=args.year_start,
        year_end=args.year_end,
        settings=settings,
        raw_dir=args.raw_dir,
        data_dir=args.data_dir,
        workers=args.workers,
        watch=args.watch,
        poll_seconds=args.poll_seconds,
    )
    print(json.dumps(counters, indent=2))
    return 0


async def _cmd_calendar(args: argparse.Namespace, settings: ScraperSettings) -> int:
    state = cast(State, args.state)
    summary = await run_calendar(
        state=state,
        year_start=args.year_start,
        year_end=args.year_end,
        month_start=args.month_start,
        month_end=args.month_end,
        settings=settings,
        raw_dir=args.raw_dir,
        data_dir=args.data_dir,
        refresh=args.refresh,
    )
    print(json.dumps(summary, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.cmd == "fixtures":
        return asyncio.run(_cmd_fixtures(args, settings))
    if args.cmd == "meeting":
        return asyncio.run(_cmd_meeting(args, settings))
    if args.cmd == "listing":
        return asyncio.run(_cmd_listing(args, settings))
    if args.cmd == "calendar":
        return asyncio.run(_cmd_calendar(args, settings))
    if args.cmd == "meetings-download":
        return asyncio.run(_cmd_meetings_download(args, settings))
    parser.error(f"unknown command {args.cmd}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
