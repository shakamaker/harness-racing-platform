"""Environment-driven scraper configuration (CLAUDE.md §4.1.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperSettings(BaseSettings):
    """Top-level scraper configuration loaded from environment + .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="SCRAPER_",
    )

    proxy_url: Annotated[HttpUrl | None, Field(default=None, alias="SCRAPER_PROXY_URL")] = None

    rate_limit_rpm: Annotated[
        int,
        Field(default=30, ge=1, le=300, alias="SCRAPER_RATE_LIMIT_RPM"),
    ] = 30
    """Token-bucket global rate limit, requests per minute."""

    workers_per_state: Annotated[
        int,
        Field(default=3, ge=1, le=10, alias="SCRAPER_WORKERS_PER_STATE"),
    ] = 3

    user_agent_pool: Annotated[
        str,
        Field(default="firefox-desktop,chrome-desktop", alias="SCRAPER_USER_AGENT_POOL"),
    ] = "firefox-desktop,chrome-desktop"

    raw_html_dir: Annotated[
        Path,
        Field(default=Path("./raw_html"), alias="RAW_HTML_DIR"),
    ] = Path("./raw_html")

    cookie_jar_dir: Annotated[
        Path,
        Field(default=Path("./.scraper_cookies"), alias="SCRAPER_COOKIE_JAR_DIR"),
    ] = Path("./.scraper_cookies")

    locale: Annotated[str, Field(default="en-AU", alias="SCRAPER_LOCALE")] = "en-AU"

    timezone_id: Annotated[
        str,
        Field(default="Australia/Melbourne", alias="SCRAPER_TIMEZONE"),
    ] = "Australia/Melbourne"

    max_retries: Annotated[int, Field(default=5, ge=0, le=10, alias="SCRAPER_MAX_RETRIES")] = 5

    request_timeout_s: Annotated[
        float,
        Field(default=30.0, ge=1.0, le=120.0, alias="SCRAPER_REQUEST_TIMEOUT_S"),
    ] = 30.0

    jitter_min_ms: Annotated[
        int,
        Field(default=800, ge=0, le=10_000, alias="SCRAPER_JITTER_MIN_MS"),
    ] = 800

    jitter_max_ms: Annotated[
        int,
        Field(default=2400, ge=0, le=20_000, alias="SCRAPER_JITTER_MAX_MS"),
    ] = 2400

    headless: Annotated[bool, Field(default=True, alias="SCRAPER_HEADLESS")] = True

    base_url: Annotated[
        str,
        Field(default="https://www.harness.org.au", alias="SCRAPER_BASE_URL"),
    ] = "https://www.harness.org.au"


def get_settings() -> ScraperSettings:
    return ScraperSettings()
