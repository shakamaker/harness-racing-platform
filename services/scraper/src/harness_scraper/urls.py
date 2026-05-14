"""URL construction for the harness.org.au monthly results grid.

The canonical results URL templated from the supplied curl is::

    https://www.harness.org.au/racing/results/
        ?month={m}&year={y}&state={s}&search_type=monthly

States in the form select use lowercase 2-3 letter codes (``vic``, ``nsw``,
``qld``, ``sa``, ``wa``, ``tas``, ``nt``, ``act``). Meeting permalinks use the
``?mc=XXXXXXX`` query and are emitted relative to ``/racing/results/`` — joining
to the base URL produces a full URL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

State = Literal["vic", "nsw", "qld", "sa", "wa", "tas", "nt", "act"]
ALL_STATES: tuple[State, ...] = ("vic", "nsw", "qld", "sa", "wa", "tas", "nt", "act")

YEAR_MIN = 1985
YEAR_MAX = 2026  # extend at the top of each new calendar year


@dataclass(frozen=True, slots=True)
class MonthlyResultsQuery:
    month: int
    year: int
    state: State

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"month out of range: {self.month}")
        if not YEAR_MIN <= self.year <= YEAR_MAX:
            raise ValueError(f"year out of range: {self.year}")
        if self.state not in ALL_STATES:
            raise ValueError(f"unknown state: {self.state}")


def build_monthly_results_url(base_url: str, q: MonthlyResultsQuery) -> str:
    """Construct the canonical monthly results URL."""
    query = urlencode(
        {"month": q.month, "year": q.year, "state": q.state, "search_type": "monthly"}
    )
    return f"{base_url.rstrip('/')}/racing/results/?{query}"


def build_meeting_url(base_url: str, meeting_href: str) -> str:
    """Join a meeting ``href`` to the base URL.

    The listing markup emits absolute-path hrefs like
    ``/racing/fields/race-fields/?mc=GE310124``, which must be appended to the
    scheme+host of ``base_url``. The CLAUDE.md spec mentions
    ``/racing/results/?mc=...`` but observation against live HTML (Jan 2024
    VIC) shows the real path is ``/racing/fields/race-fields/``. We honour the
    href as-given rather than rewriting the path.
    """
    href = meeting_href.strip()
    if href.startswith("http"):
        return href
    base = base_url.rstrip("/")
    if href.startswith("/"):
        return f"{base}{href}"
    if href.startswith("?"):
        # Bare-query href without a path — apply the legacy results path.
        return f"{base}/racing/results/{href}"
    return urljoin(f"{base}/racing/results/", href)


def extract_meeting_code(meeting_href_or_url: str) -> str | None:
    """Pull the ``mc=`` query value out of a meeting href or full URL.

    Returns ``None`` if the input has no ``mc`` query parameter; this lets the
    caller decide whether to raise or skip a malformed listing row.
    """
    value = meeting_href_or_url.strip()
    if "?" not in value:
        return None
    qs = value.split("?", 1)[1]
    # urlparse handles trailing fragments correctly even when given a bare query.
    parsed = urlparse(f"http://x/?{qs}")
    mc = parse_qs(parsed.query).get("mc")
    return mc[0] if mc else None


def iter_grid(
    states: tuple[State, ...] = ALL_STATES,
    *,
    year_min: int = YEAR_MIN,
    year_max: int = YEAR_MAX,
    months: tuple[int, ...] = tuple(range(1, 13)),
) -> list[MonthlyResultsQuery]:
    """Materialise every (state, year, month) tuple in canonical iteration order.

    Order: state-outer, year-descending, month-ascending. Recent data first so
    a partial run still produces something fresh.
    """
    out: list[MonthlyResultsQuery] = []
    for state in states:
        for year in range(year_max, year_min - 1, -1):
            for month in months:
                out.append(MonthlyResultsQuery(month=month, year=year, state=state))
    return out
