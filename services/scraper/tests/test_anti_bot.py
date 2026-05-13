"""Tests for the anti-bot stack: profile pool, jitter, blockpage detection."""

from __future__ import annotations

import random

import pytest

from harness_scraper.anti_bot import (
    BlockedError,
    detect_blockpage,
    gaussian_delay_ms,
    pick_profile,
)


class TestPickProfile:
    def test_returns_known_profile(self) -> None:
        profile = pick_profile("firefox-desktop")
        assert profile.label == "firefox-desktop"
        assert "Firefox" in profile.user_agent

    def test_falls_back_when_pool_invalid(self) -> None:
        profile = pick_profile("bogus,unknown")
        assert profile.label == "firefox-desktop"

    def test_pool_filters_unknowns(self) -> None:
        rng = random.Random(0)
        # 100 picks from a partly-invalid pool must all land on valid profiles.
        for _ in range(100):
            p = pick_profile("firefox-desktop, garbage, chrome-desktop", rng=rng)
            assert p.label in {"firefox-desktop", "chrome-desktop"}


class TestGaussianDelay:
    def test_within_bounds(self) -> None:
        rng = random.Random(42)
        for _ in range(1000):
            d = gaussian_delay_ms(800, 2400, rng=rng)
            assert 800 <= d <= 2400

    def test_zero_range_returns_constant(self) -> None:
        assert gaussian_delay_ms(1000, 1000) == 1000

    def test_inverted_bounds_rejected(self) -> None:
        with pytest.raises(ValueError):
            gaussian_delay_ms(2000, 1000)


class TestDetectBlockpage:
    def test_real_listing_passes(self) -> None:
        # Genuine listing pages mention "captcha" in the Mura CMS init JS.
        # The detector must NOT trigger on that.
        html = """
        <html><body>
        <script>var Mura = {reCAPTCHALanguage:'en'};</script>
        <table class="meetingListFull">
          <tr><td>Geelong</td></tr>
        </table>
        </body></html>
        """
        detect_blockpage(html, url="https://example/", status=200)  # no raise

    def test_cloudflare_just_a_moment_triggers(self) -> None:
        html = "<html><body>Just a moment... checking your browser...</body></html>"
        with pytest.raises(BlockedError) as ei:
            detect_blockpage(html, url="https://example/", status=200)
        assert "just a moment..." in ei.value.marker

    def test_soft_marker_only_on_bad_status(self) -> None:
        html = "<html><body>Access denied</body></html>"
        # 200 → not raised
        detect_blockpage(html, status=200)
        # 403 → raised
        with pytest.raises(BlockedError):
            detect_blockpage(html, status=403)

    def test_empty_html_raises(self) -> None:
        with pytest.raises(BlockedError):
            detect_blockpage("", status=200)

    def test_sample_includes_context(self) -> None:
        html = "padding " * 10 + "are you a human?" + " padding " * 10
        with pytest.raises(BlockedError) as ei:
            detect_blockpage(html)
        assert "human" in ei.value.sample.lower()
