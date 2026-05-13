"""Playwright session wrapper applying the anti-bot stack (CLAUDE.md §4.1.2)."""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from harness_scraper.anti_bot import (
    STEALTH_INIT_SCRIPT,
    BlockedError,
    BrowserProfile,
    detect_blockpage,
    gaussian_delay_ms,
    pick_profile,
)
from harness_scraper.cookie_jar import resolve_jar
from harness_scraper.logging_setup import get_logger
from harness_scraper.settings import ScraperSettings

log = get_logger(__name__)


@dataclass(slots=True)
class FetchResult:
    url: str
    status: int
    html: str
    profile_label: str
    elapsed_ms: int


class HarnessBrowser:
    """Long-lived Playwright session for one (profile × state) pair.

    Designed for a small async worker pool — instantiate once per state, reuse
    across many fetches so cookies and the storage_state accumulate.
    """

    def __init__(
        self,
        settings: ScraperSettings,
        *,
        session_id: str,
        rng: random.Random | None = None,
    ) -> None:
        self._settings = settings
        self._session_id = session_id
        self._rng = rng or random.SystemRandom()
        self._profile: BrowserProfile = pick_profile(settings.user_agent_pool, self._rng)
        self._jar = resolve_jar(settings.cookie_jar_dir, session_id)
        self._last_url: str | None = None
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @property
    def profile(self) -> BrowserProfile:
        return self._profile

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        # Chromium covers both Firefox and Chrome UA personae. Spec calls out
        # rotating UA, viewport, etc. — the underlying engine being Chromium
        # is fine because the wire signature is what the server inspects.
        self._browser = await self._pw.chromium.launch(
            headless=self._settings.headless,
            proxy=(
                {"server": str(self._settings.proxy_url)}
                if self._settings.proxy_url
                else None
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        storage_state = self._jar.load()
        self._context = await self._browser.new_context(
            user_agent=self._profile.user_agent,
            viewport=self._profile.viewport,  # type: ignore[arg-type]
            locale=self._settings.locale,
            timezone_id=self._settings.timezone_id,
            extra_http_headers={
                "Accept": self._profile.accept,
                "Accept-Language": self._profile.accept_language,
                # Note: Accept-Encoding is generally managed by the browser
                # itself, but we pass it through for fingerprint parity.
                "Accept-Encoding": self._profile.accept_encoding,
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Priority": "u=0, i",
            },
            storage_state=storage_state,  # type: ignore[arg-type]
        )
        await self._context.add_init_script(STEALTH_INIT_SCRIPT)
        log.info(
            "browser_started",
            session_id=self._session_id,
            profile=self._profile.label,
            has_jar=storage_state is not None,
            proxy=bool(self._settings.proxy_url),
        )

    async def close(self) -> None:
        try:
            if self._context is not None:
                state = await self._context.storage_state()
                self._jar.save(state)
                await self._context.close()
        finally:
            if self._browser is not None:
                await self._browser.close()
            if self._pw is not None:
                await self._pw.stop()
            self._context = None
            self._browser = None
            self._pw = None

    @asynccontextmanager
    async def _page(self) -> AsyncIterator[Page]:
        if self._context is None:
            raise RuntimeError("HarnessBrowser.start() must be called before fetching")
        page = await self._context.new_page()
        try:
            yield page
        finally:
            await page.close()

    async def fetch(self, url: str, *, referer: str | None = None) -> FetchResult:
        """Navigate to ``url`` with jitter + stealth, return HTML on 2xx.

        Raises :class:`BlockedError` if a captcha / blockpage is detected and
        re-raises any Playwright timeout / navigation error verbatim so the
        retry decorator can decide.
        """
        if self._context is None:
            raise RuntimeError("HarnessBrowser.start() must be called before fetching")

        delay_ms = gaussian_delay_ms(
            self._settings.jitter_min_ms, self._settings.jitter_max_ms, rng=self._rng
        )
        await asyncio.sleep(delay_ms / 1000.0)

        ref = referer or self._last_url

        loop = asyncio.get_running_loop()
        t0 = loop.time()

        async with self._page() as page:
            if ref:
                # Setting Referer via route override works regardless of the
                # browser engine. We attach it for the first request only.
                await page.set_extra_http_headers({"Referer": ref})

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(self._settings.request_timeout_s * 1000),
            )
            status = response.status if response else 0
            html = await page.content()

        elapsed_ms = int((loop.time() - t0) * 1000)
        log.info(
            "fetch_complete",
            url=url,
            status=status,
            elapsed_ms=elapsed_ms,
            profile=self._profile.label,
            jitter_ms=delay_ms,
        )

        try:
            detect_blockpage(html, url=url, status=status)
        except BlockedError as exc:
            log.error(
                "blocked",
                url=url,
                marker=exc.marker,
                sample=exc.sample,
                status=status,
                outcome="blocked",
            )
            raise

        if status >= 400:
            log.warning("http_error", url=url, status=status, outcome="http_error")

        self._last_url = url
        return FetchResult(
            url=url,
            status=status,
            html=html,
            profile_label=self._profile.label,
            elapsed_ms=elapsed_ms,
        )

    async def __aenter__(self) -> "HarnessBrowser":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
