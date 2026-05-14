"""Anti-bot subterfuge stack for Playwright (CLAUDE.md §4.1.2).

This module owns:

* User-Agent + viewport + Accept-* pool, templated from the curl in
  ``docs/sample-curl.txt`` so the live signature matches a real Firefox session.
* Playwright stealth patches (``navigator.webdriver = false``, plugin/WebGL/
  canvas fingerprint spoofing).
* Gaussian-jittered inter-navigation delay.
* Captcha / blockpage detection — raises ``BlockedError`` so callers route to
  the ``error_log`` table per CLAUDE.md §5.2.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

# Templated from the supplied curl. We keep two complete realistic profiles
# (Firefox-desktop + Chrome-desktop) and rotate per session, never per request,
# so a single browsing session looks internally consistent.
_FIREFOX_PROFILE: Final = {
    "label": "firefox-desktop",
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) "
        "Gecko/20100101 Firefox/150.0"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept_language": "en-US,en;q=0.9",
    "accept_encoding": "gzip, deflate, br, zstd",
    "viewport": {"width": 1920, "height": 1080},
    "sec_ch_ua": None,
}

_CHROME_PROFILE: Final = {
    "label": "chrome-desktop",
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept_language": "en-AU,en-US;q=0.9,en;q=0.8",
    "accept_encoding": "gzip, deflate, br, zstd",
    "viewport": {"width": 1536, "height": 864},
    "sec_ch_ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
}

_PROFILES: Final[dict[str, dict]] = {
    "firefox-desktop": _FIREFOX_PROFILE,
    "chrome-desktop": _CHROME_PROFILE,
}


# Distinctive blockpage / interstitial phrases. Each is uniquely associated
# with a real challenge page and does NOT appear in legitimate harness.org.au
# HTML. Generic terms like "captcha" or "cloudflare" are intentionally NOT
# here because the live site embeds them in inline JS (e.g. Mura CMS exposes
# ``reCAPTCHALanguage:"en"``, which is a config string not a real challenge).
_BLOCKPAGE_MARKERS: Final = (
    "just a moment...",
    "checking your browser before accessing",
    "ddos protection by",
    "attention required! | cloudflare",
    "are you a human?",
    "please complete the security check",
    "enable javascript and cookies to continue",
)

# Markers we accept ONLY when the HTTP status is itself suspicious (403/429/
# 503). They appear in legitimate content too often to be standalone signals.
_BLOCKPAGE_MARKERS_SOFT: Final = (
    "access denied",
    "request blocked",
    "you have been blocked",
)
_SOFT_TRIGGER_STATUSES: Final = frozenset({403, 429, 503})


class BlockedError(RuntimeError):
    """Raised when a fetched page looks like a captcha / blockpage."""

    def __init__(self, *, url: str, marker: str, sample: str) -> None:
        super().__init__(f"blocked on {url}: matched marker {marker!r}")
        self.url = url
        self.marker = marker
        self.sample = sample


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    label: str
    user_agent: str
    accept: str
    accept_language: str
    accept_encoding: str
    viewport: dict[str, int]
    sec_ch_ua: str | None


def pick_profile(pool: str, rng: random.Random | None = None) -> BrowserProfile:
    """Pick a profile from a comma-separated label pool.

    Unknown labels are silently filtered (warn-level logging is the caller's
    job) — the function never raises so a misconfigured ``SCRAPER_USER_AGENT_POOL``
    can't crash startup.
    """
    rng = rng or random.SystemRandom()
    labels = [s.strip() for s in pool.split(",") if s.strip() in _PROFILES]
    if not labels:
        labels = ["firefox-desktop"]
    choice = rng.choice(labels)
    return _to_profile(_PROFILES[choice])


def _to_profile(d: dict) -> BrowserProfile:
    return BrowserProfile(
        label=d["label"],
        user_agent=d["user_agent"],
        accept=d["accept"],
        accept_language=d["accept_language"],
        accept_encoding=d["accept_encoding"],
        viewport=d["viewport"],
        sec_ch_ua=d.get("sec_ch_ua"),
    )


# ---------------------------------------------------------------------------
# Jitter
# ---------------------------------------------------------------------------


def gaussian_delay_ms(
    min_ms: int, max_ms: int, *, rng: random.Random | None = None
) -> int:
    """Return a delay in milliseconds drawn from a clipped Gaussian.

    Mean is the midpoint; stddev is one-sixth of the range so ~99.7% of draws
    fall inside [min, max] before clipping. Clipping at the bounds prevents
    pathological outliers (the spec wants 800–2400ms per §4.1.2).
    """
    rng = rng or random.SystemRandom()
    if min_ms > max_ms:
        raise ValueError(f"min_ms ({min_ms}) > max_ms ({max_ms})")
    if min_ms == max_ms:
        return min_ms
    mean = (min_ms + max_ms) / 2
    stddev = (max_ms - min_ms) / 6
    sample = rng.gauss(mean, stddev)
    return max(min_ms, min(max_ms, int(sample)))


# ---------------------------------------------------------------------------
# Stealth init script — runs before any page JS, masks Playwright signatures.
# ---------------------------------------------------------------------------


STEALTH_INIT_SCRIPT: Final = """
// Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// Plugins length spoof (Firefox/Chrome both report >= 1 in normal sessions)
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3, 4, 5].map(() => ({}))
});

// Languages: align with Accept-Language header
Object.defineProperty(navigator, 'languages', {
  get: () => ['en-AU', 'en-US', 'en']
});

// WebGL vendor/renderer fingerprint normalisation
const _origGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (parameter) {
  // UNMASKED_VENDOR_WEBGL
  if (parameter === 37445) return 'Intel Inc.';
  // UNMASKED_RENDERER_WEBGL
  if (parameter === 37446) return 'Intel Iris OpenGL Engine';
  return _origGetParameter.call(this, parameter);
};

// Canvas fingerprint perturbation — adds 1-bit noise to toDataURL output so
// fingerprinters can't dedupe across sessions.
const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function (...args) {
  const ctx = this.getContext('2d');
  if (ctx) {
    const w = this.width, h = this.height;
    if (w > 0 && h > 0) {
      try {
        const img = ctx.getImageData(0, 0, w, h);
        // Flip the LSB of one random pixel's red channel
        const idx = (Math.floor(Math.random() * w * h)) * 4;
        img.data[idx] = img.data[idx] ^ 1;
        ctx.putImageData(img, 0, 0);
      } catch (_) { /* canvas tainted by CORS — ignore */ }
    }
  }
  return _origToDataURL.apply(this, args);
};

// Permissions API: align notification permission with a real browser
const _origQuery = navigator.permissions && navigator.permissions.query;
if (_origQuery) {
  navigator.permissions.query = (params) =>
    params.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : _origQuery.call(navigator.permissions, params);
}
"""


# ---------------------------------------------------------------------------
# Blockpage detection
# ---------------------------------------------------------------------------


def detect_blockpage(html: str, *, url: str = "<unknown>", status: int = 200) -> None:
    """Raise ``BlockedError`` if the response looks like a captcha / interstitial.

    Two-tier check:

    1. Hard markers (unique to challenge pages) → raise on any status.
    2. Soft markers (could legitimately appear in CMS content) → raise only
       when ``status`` is itself a suspicious code (403/429/503).

    Empty HTML is treated as a hard block. False positives are expensive
    (they halt the queue per CLAUDE.md §5.2) so we err on the conservative
    side.
    """
    if not html:
        raise BlockedError(url=url, marker="<empty body>", sample="")
    haystack = html.lower()

    for marker in _BLOCKPAGE_MARKERS:
        if marker in haystack:
            idx = haystack.find(marker)
            start = max(0, idx - 40)
            end = min(len(html), idx + 160)
            raise BlockedError(url=url, marker=marker, sample=html[start:end])

    if status in _SOFT_TRIGGER_STATUSES:
        for marker in _BLOCKPAGE_MARKERS_SOFT:
            if marker in haystack:
                idx = haystack.find(marker)
                start = max(0, idx - 40)
                end = min(len(html), idx + 160)
                raise BlockedError(
                    url=url, marker=f"{marker} (status={status})", sample=html[start:end]
                )
