"""Bulk per-meeting HTML downloader (CLAUDE.md §4.1.4–§4.1.5).

Consumes the year manifests produced by :mod:`harness_scraper.calendar`,
fans the per-meeting fetches out across an async worker pool, and persists
each meeting's raw HTML under ``RAW_HTML_DIR/{state}/{year}/{mc}.html``.

Resumable: any meeting whose HTML file already exists on disk is skipped.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from harness_scraper.browser import HarnessBrowser
from harness_scraper.fetcher import fetch_meeting_html
from harness_scraper.logging_setup import get_logger
from harness_scraper.rate_limit import TokenBucket
from harness_scraper.settings import ScraperSettings
from harness_scraper.urls import MonthlyResultsQuery, State, build_monthly_results_url

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _Job:
    state: State
    year: int
    meeting_code: str
    meeting_href: str
    referer: str


def _load_manifest(path: Path, *, state: State, year: int, base_url: str) -> list[_Job]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    referer = build_monthly_results_url(
        base_url, MonthlyResultsQuery(month=1, year=year, state=state)
    )
    jobs: list[_Job] = []
    for row in rows:
        code = row["meeting_code"]
        href = row["meeting_href"]
        jobs.append(
            _Job(
                state=state,
                year=year,
                meeting_code=code,
                meeting_href=href,
                referer=referer,
            )
        )
    return jobs


def _existing_html_path(raw_dir: Path, state: State, year: int, code: str) -> Path:
    return raw_dir / state / str(year) / f"{code}.html"


async def _worker(
    name: str,
    queue: asyncio.Queue[_Job | None],
    browser: HarnessBrowser,
    rate_limiter: TokenBucket,
    settings: ScraperSettings,
    counters: dict[str, int],
) -> None:
    while True:
        job = await queue.get()
        try:
            if job is None:
                return
            try:
                _result, _path = await fetch_meeting_html(
                    browser,
                    meeting_code=job.meeting_code,
                    meeting_href=job.meeting_href,
                    state=job.state,
                    year=job.year,
                    settings=settings,
                    rate_limiter=rate_limiter,
                    referer=job.referer,
                )
                counters["downloaded"] += 1
            except Exception as exc:  # noqa: BLE001 — we log and continue
                counters["failed"] += 1
                log.error(
                    "meeting_download_failed",
                    worker=name,
                    meeting_code=job.meeting_code,
                    state=job.state,
                    year=job.year,
                    error=str(exc),
                    outcome="failed",
                )
        finally:
            queue.task_done()


def _enqueue_pending(
    *,
    state: State,
    year_start: int,
    year_end: int,
    base_url: str,
    raw_dir: Path,
    data_dir: Path,
    queue: asyncio.Queue[_Job | None],
    counters: dict[str, int],
    enqueued_keys: set[tuple[int, str]],
) -> int:
    """Scan manifests in [year_start, year_end] and enqueue any meetings whose
    HTML is missing and which haven't been enqueued already. Returns the
    number of jobs added this pass."""
    added = 0
    for year in range(year_start, year_end + 1):
        manifest = data_dir / "calendar" / state / f"{year}.json"
        if not manifest.is_file():
            continue
        try:
            jobs = _load_manifest(manifest, state=state, year=year, base_url=base_url)
        except (OSError, ValueError) as exc:
            log.warning(
                "manifest_unreadable",
                state=state,
                year=year,
                path=str(manifest),
                error=str(exc),
            )
            continue
        for job in jobs:
            key = (year, job.meeting_code)
            if key in enqueued_keys:
                continue
            if _existing_html_path(raw_dir, state, year, job.meeting_code).exists():
                counters["skipped"] += 1
                enqueued_keys.add(key)
                continue
            enqueued_keys.add(key)
            queue.put_nowait(job)
            counters["queued"] += 1
            added += 1
    return added


async def run_meeting_downloads(
    *,
    state: State,
    year_start: int,
    year_end: int,
    settings: ScraperSettings,
    raw_dir: Path,
    data_dir: Path,
    workers: int | None = None,
    watch: bool = False,
    poll_seconds: float = 30.0,
    idle_passes_before_exit: int = 4,
) -> dict:
    """Download per-meeting HTML for every meeting in the year-range manifests.

    When ``watch`` is True the runner re-scans manifests every ``poll_seconds``
    and exits only after ``idle_passes_before_exit`` consecutive passes find
    no new work. Used to ride alongside a calendar scrape that publishes
    year manifests over time.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    rate_limiter = TokenBucket(rate_per_minute=settings.rate_limit_rpm)
    worker_count = max(1, workers or settings.workers_per_state)

    counters: dict[str, int] = {"queued": 0, "skipped": 0, "downloaded": 0, "failed": 0}
    queue: asyncio.Queue[_Job | None] = asyncio.Queue()
    enqueued_keys: set[tuple[int, str]] = set()

    added = _enqueue_pending(
        state=state,
        year_start=year_start,
        year_end=year_end,
        base_url=settings.base_url,
        raw_dir=raw_dir,
        data_dir=data_dir,
        queue=queue,
        counters=counters,
        enqueued_keys=enqueued_keys,
    )
    log.info(
        "meeting_download_plan",
        state=state,
        year_start=year_start,
        year_end=year_end,
        queued=counters["queued"],
        skipped=counters["skipped"],
        workers=worker_count,
        watch=watch,
    )

    if added == 0 and not watch:
        return counters

    async with HarnessBrowser(settings, session_id=f"meetings-{state}") as browser:
        workers_tasks = [
            asyncio.create_task(
                _worker(f"w{i}", queue, browser, rate_limiter, settings, counters),
                name=f"meeting-worker-{i}",
            )
            for i in range(worker_count)
        ]

        if watch:
            idle_passes = 0
            while True:
                await queue.join()
                new_jobs = _enqueue_pending(
                    state=state,
                    year_start=year_start,
                    year_end=year_end,
                    base_url=settings.base_url,
                    raw_dir=raw_dir,
                    data_dir=data_dir,
                    queue=queue,
                    counters=counters,
                    enqueued_keys=enqueued_keys,
                )
                if new_jobs == 0:
                    idle_passes += 1
                    log.info(
                        "meeting_download_idle",
                        state=state,
                        idle_passes=idle_passes,
                        downloaded=counters["downloaded"],
                        failed=counters["failed"],
                    )
                    if idle_passes >= idle_passes_before_exit:
                        break
                else:
                    idle_passes = 0
                    log.info(
                        "meeting_download_new_work",
                        state=state,
                        new_jobs=new_jobs,
                        queued_total=counters["queued"],
                    )
                await asyncio.sleep(poll_seconds)
        else:
            await queue.join()

        for _ in range(worker_count):
            await queue.put(None)
        await asyncio.gather(*workers_tasks, return_exceptions=True)

    log.info("meeting_download_complete", state=state, **counters)
    return counters
