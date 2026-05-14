"""High-level fetch orchestration (CLAUDE.md §4.1.4, §4.1.5).

Wraps :class:`HarnessBrowser` with:

* token-bucket rate limiting
* tenacity-backed exponential backoff on 403/429/503 and Playwright timeouts
* on-disk persistence of raw HTML under ``RAW_HTML_DIR/{state}/{year}/...``

The two public entry points are:

* :func:`fetch_monthly_listing` — pull a state-year-month listing page and
  return its HTML for :func:`harness_scraper.meetings.extract_meetings`.
* :func:`fetch_meeting_html` — pull a single meeting permalink and persist
  the raw HTML to ``RAW_HTML_DIR``.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from harness_scraper.anti_bot import BlockedError
from harness_scraper.browser import FetchResult, HarnessBrowser
from harness_scraper.logging_setup import get_logger
from harness_scraper.rate_limit import TokenBucket
from harness_scraper.settings import ScraperSettings
from harness_scraper.urls import (
    MonthlyResultsQuery,
    State,
    build_meeting_url,
    build_monthly_results_url,
)

log = get_logger(__name__)


class TransientHttpError(RuntimeError):
    """Wraps a fetch that returned a retryable HTTP status (403/429/503)."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} on {url}")
        self.status = status
        self.url = url


_RETRYABLE_STATUSES = frozenset({403, 408, 425, 429, 500, 502, 503, 504})


def _maybe_retryable(result: FetchResult) -> None:
    if result.status in _RETRYABLE_STATUSES:
        raise TransientHttpError(result.status, result.url)


async def _retrying(
    coro_fn,
    *,
    settings: ScraperSettings,
):
    """tenacity-driven retry wrapper. ``coro_fn`` is an async callable taking
    the attempt number and returning a :class:`FetchResult`.
    """
    retryer = AsyncRetrying(
        stop=stop_after_attempt(settings.max_retries + 1),
        wait=wait_random_exponential(multiplier=1.5, min=1, max=30),
        retry=retry_if_exception_type(
            (TransientHttpError, PlaywrightTimeoutError, PlaywrightError, BlockedError)
        ),
        reraise=True,
    )
    attempt_n = 0
    async for attempt in retryer:
        with attempt:
            attempt_n += 1
            return await coro_fn(attempt_n)
    raise RuntimeError("unreachable: AsyncRetrying exited without producing a result")


async def fetch_monthly_listing(
    browser: HarnessBrowser,
    query: MonthlyResultsQuery,
    *,
    settings: ScraperSettings,
    rate_limiter: TokenBucket,
    referer: str | None = None,
) -> FetchResult:
    """Fetch one monthly results listing page with retries + rate limiting."""
    url = build_monthly_results_url(settings.base_url, query)

    async def _one(attempt: int) -> FetchResult:
        await rate_limiter.acquire()
        log.info(
            "listing_fetch_start",
            state=query.state,
            year=query.year,
            month=query.month,
            url=url,
            attempt=attempt,
        )
        result = await browser.fetch(url, referer=referer)
        _maybe_retryable(result)
        log.info(
            "listing_fetch_ok",
            state=query.state,
            year=query.year,
            month=query.month,
            status=result.status,
            elapsed_ms=result.elapsed_ms,
            attempt=attempt,
            outcome="ok",
        )
        return result

    try:
        return await _retrying(_one, settings=settings)
    except RetryError as exc:  # pragma: no cover — reraise path
        log.error(
            "listing_fetch_exhausted",
            state=query.state,
            year=query.year,
            month=query.month,
            url=url,
            outcome="exhausted",
        )
        raise exc.last_attempt.exception() from exc


async def fetch_meeting_html(
    browser: HarnessBrowser,
    meeting_code: str,
    meeting_href: str,
    *,
    state: State,
    year: int,
    settings: ScraperSettings,
    rate_limiter: TokenBucket,
    referer: str | None = None,
) -> tuple[FetchResult, Path]:
    """Fetch one meeting page and persist its HTML under ``RAW_HTML_DIR``."""
    url = build_meeting_url(settings.base_url, meeting_href)
    out_dir = settings.raw_html_dir / state / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{meeting_code}.html"

    async def _one(attempt: int) -> FetchResult:
        await rate_limiter.acquire()
        t0 = time.monotonic()
        log.info(
            "meeting_fetch_start",
            meeting_code=meeting_code,
            state=state,
            year=year,
            url=url,
            attempt=attempt,
        )
        result = await browser.fetch(url, referer=referer)
        _maybe_retryable(result)
        out_path.write_text(result.html, encoding="utf-8")
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "meeting_fetch_ok",
            meeting_code=meeting_code,
            state=state,
            year=year,
            html_path=str(out_path),
            bytes=len(result.html),
            elapsed_ms=elapsed_ms,
            attempt=attempt,
            outcome="ok",
        )
        return result

    try:
        result = await _retrying(_one, settings=settings)
    except RetryError as exc:  # pragma: no cover
        log.error(
            "meeting_fetch_exhausted",
            meeting_code=meeting_code,
            state=state,
            year=year,
            url=url,
            outcome="exhausted",
        )
        raise exc.last_attempt.exception() from exc
    return result, out_path
