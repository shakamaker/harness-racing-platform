"""Parse a meeting result HTML page into a :class:`MeetingDTO` (CLAUDE.md §4.2).

The shape of the source HTML is documented in
``C:\\Users\\franc\\wagon-apollo\\claude\\Raceday v2.0\\docs\\
pertinent_html_sample_and_parsing_indication.txt`` and confirmed by inspecting
``raw_html/vic/2024/GE310124.html`` (Geelong 31 Jan 2024).

Each meeting page contains N races; for each race:

* ``table.raceMoreInfo`` → race header (race_number, race_time, race_name,
  distance, conditions/purse/age/class/gait/start_type, final/interim flag).
* ``table.raceFieldTable.resultTable`` → finisher rows.
* ``table.raceTimes`` → track rating, gross/mile/lead times, quarters, margins.

The three tables appear in document order, 1:1:1; we iterate them together.

The parser is built on :mod:`selectolax` for speed and falls back to ``re``
for the conditions block (free-form prose that's easier to slice with regex).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Final, Iterable

from selectolax.parser import HTMLParser, Node

from harness_parser.dtos import (
    DayNight,
    MeetingDTO,
    RaceDTO,
    RaceTimesDTO,
    RunnerDTO,
    StewardsCommentDTO,
)
from harness_parser.time_utils import TimeParseError, to_ss_ms

__all__ = ["parse_results_html", "MeetingParseError"]


class MeetingParseError(ValueError):
    """Raised when the HTML cannot be parsed into a meeting structure.

    The parser is intentionally lenient at the row level (per-race / per-runner
    issues become None fields + structured log lines), and strict only when
    the page itself is unusable (no race headers, no meeting heading).
    """


_WHITESPACE_RE: Final = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    if text is None:
        return ""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_html(s: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", s))


# ---------------------------------------------------------------------------
# Meeting-level metadata
# ---------------------------------------------------------------------------

# Page header looks like: "Geelong (Night) - Wednesday, 31 January 2024".
_MEETING_HEADER_RE: Final = re.compile(
    r"^(?P<track>.+?)\s*"
    r"(?:\((?P<day_night>Day|Night|Twilight|Matinee)\))?"
    r"\s*[-–]\s*"
    r"(?P<weekday>Sun|Mon|Tue|Wed|Thu|Fri|Sat|Sunday|Monday|Tuesday|"
    r"Wednesday|Thursday|Friday|Saturday),?\s*"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+"
    r"(?P<year>\d{4})\s*$",
    re.IGNORECASE,
)


def _parse_meeting_heading(tree: HTMLParser) -> tuple[str | None, DayNight, date | None]:
    """Extract ``(track_name, day_night, meeting_date)`` from the page header.

    Returns triple of ``None`` if the heading isn't found — caller may fall
    back to manifest-derived values.
    """
    for tag in ("h2", "h1"):
        for node in tree.css(tag):
            text = _clean(node.text())
            m = _MEETING_HEADER_RE.match(text)
            if not m:
                continue
            track = _clean(m.group("track"))
            day_night_raw = (m.group("day_night") or "").upper()
            day_night: DayNight
            if day_night_raw == "DAY":
                day_night = "DAY"
            elif day_night_raw == "NIGHT":
                day_night = "NIGHT"
            elif day_night_raw == "TWILIGHT" or day_night_raw == "MATINEE":
                day_night = "TWILIGHT"
            else:
                day_night = "UNKNOWN"
            try:
                meeting_date = datetime.strptime(
                    f"{int(m.group('day'))} {m.group('month')} {m.group('year')}",
                    "%d %B %Y",
                ).date()
            except ValueError:
                meeting_date = None
            return track, day_night, meeting_date
    return None, "UNKNOWN", None


# ---------------------------------------------------------------------------
# Race header (table.raceMoreInfo)
# ---------------------------------------------------------------------------

_DISTANCE_RE: Final = re.compile(r"(\d+)")
_PURSE_RE: Final = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
_AGE_CLASS_RE: Final = re.compile(
    r"\b(\d+ ?YO(?: and older| & older| only)?(?: mares?| colts?| geldings?| fillies?)?)\b",
    re.IGNORECASE,
)
_NR_CLASS_RE: Final = re.compile(
    r"\b(NR(?:\s+(?:up\s+to|from|of))?\s+\d+(?:\s+(?:to|or)\s+\d+)?(?:\s+or\s+better)?)\b",
    re.IGNORECASE,
)
_NUMBERED_CLASS_RE: Final = re.compile(r"\b([CR]\d+\s+only|MAIDEN|FFA|FREE FOR ALL)\b", re.IGNORECASE)
_GAIT_TERMS: Final = {"PACE", "PACERS", "TROT", "TROTTERS", "TROTTING"}
_START_TERMS: Final = {"MOBILE", "STANDING", "STANDING START"}


def _parse_race_header(table: Node) -> dict:
    """Pull race_number, race_time, race_name, distance and conditions block."""
    race_number = None
    race_time = None
    race_name = None
    distance_m = None

    rn = table.css_first("td.raceNumber")
    if rn is not None:
        m = re.search(r"\d+", _clean(rn.text()))
        if m:
            race_number = int(m.group(0))

    rt = table.css_first("td.raceTime")
    if rt is not None:
        race_time = _clean(rt.text()) or None

    title = table.css_first("td.raceTitle")
    if title is not None:
        race_name = _clean(title.text()) or None

    dist = table.css_first("td.distance")
    if dist is not None:
        m = _DISTANCE_RE.search(dist.text())
        if m:
            distance_m = int(m.group(1))

    info = table.css_first("td.raceInformation")
    conditions = _clean(info.text()) if info is not None else ""

    is_final = table.css_first("td.finalResult") is not None

    return {
        "race_number": race_number,
        "race_time": race_time,
        "race_name": race_name,
        "distance_m": distance_m,
        "conditions": conditions,
        "is_final": is_final,
    }


def _split_conditions(text: str) -> dict:
    """Slice the free-form ``raceInformation`` text into structured fields.

    The block looks like::

        $4,500
        NR up to 45.
        PBD/NR.
        TROTTERS.
        Mobile

    Order varies. We do permissive regex slicing — fields not matched stay
    ``None`` so the parser keeps moving rather than failing the race.
    """
    out: dict = {
        "race_purse": None,
        "class_name": None,
        "age_class": None,
        "race_type": None,
        "race_gait": None,
        "start_type": None,
    }
    if not text:
        return out

    if m := _PURSE_RE.search(text):
        try:
            out["race_purse"] = float(m.group(1).replace(",", ""))
        except ValueError:
            out["race_purse"] = None

    if m := _AGE_CLASS_RE.search(text):
        out["age_class"] = m.group(1).strip()

    if m := _NR_CLASS_RE.search(text):
        out["class_name"] = m.group(1).strip()
    elif m := _NUMBERED_CLASS_RE.search(text):
        out["class_name"] = m.group(1).strip()

    upper = text.upper()
    for term in _GAIT_TERMS:
        if term in upper:
            out["race_gait"] = "PACERS" if "PAC" in term else "TROTTERS"
            break

    # Both forms are seen: "Standing Start", "Standing", or "Stand" (abbrev.).
    if re.search(r"\bSTANDING\b|\bSTAND\b", upper):
        out["start_type"] = "Standing Start"
    elif "MOBILE" in upper:
        out["start_type"] = "Mobile"

    # race_type heuristic: PBD/RBD/NR-style tokens.
    if rt := re.search(r"\b(PBD|RBD|FFA|NMW|NR|PNR|RBD/NR|PBD/NR)\b", text):
        out["race_type"] = rt.group(1).upper()

    return out


# ---------------------------------------------------------------------------
# Runner table (table.raceFieldTable.resultTable)
# ---------------------------------------------------------------------------

_HORSE_ID_RE: Final = re.compile(r"horseId=(\d+)")
_TRAINER_LINK_RE: Final = re.compile(r"/racing/trainerlink/([A-Za-z0-9]+)")
_DRIVER_LINK_RE: Final = re.compile(r"/racing/driverlink/([A-Za-z0-9]+)")
_PLACE_RE: Final = re.compile(r"^\*?(\d+)$")
_MARGIN_NUMERIC_RE: Final = re.compile(r"-?\d+(?:\.\d+)?")
_PRICE_RE: Final = re.compile(r"\$?\s*([\d.]+)")
_PRIZEMONEY_RE: Final = re.compile(r"\$?\s*([\d,]+(?:\.\d{1,2})?)")


_BARRIER_INT_RE: Final = re.compile(r"\d+")


def _barrier_to_int(raw: str | None) -> int | None:
    """Extract the leading integer from a barrier label.

    ``"Fr7"`` → 7, ``"1A"`` → 1, ``"9B"`` → 9, ``"FP"`` / ``"SR"`` → ``None``.
    The integer captures the barrier *position* (front-row 7, second-row 1A
    starts at 1, etc). Non-numeric barriers like ``"FP"`` (Front-Row Penalty)
    and ``"SR"`` (Second-Row generic) have no positional index — caller falls
    back to ``barrier_raw`` for display.
    """
    if not raw:
        return None
    m = _BARRIER_INT_RE.search(raw)
    return int(m.group(0)) if m else None


def _parse_link_token(href: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(href or "")
    return m.group(1) if m else None


def _parse_decimal(text: str, *, regex: re.Pattern[str] = _PRIZEMONEY_RE) -> float | None:
    m = regex.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_place(text: str) -> tuple[int | None, bool]:
    """Return ``(finish_position, null_run)``.

    A leading ``*`` denotes a null-run finisher whose margin should be tracked
    as ``raw_margin`` and excluded from par-time aggregation.
    """
    cleaned = _clean(text)
    if not cleaned:
        return None, False
    null = cleaned.startswith("*")
    digits = cleaned.lstrip("*")
    m = _PLACE_RE.match(digits if not null else f"{digits}")
    if not m:
        return None, null
    return int(m.group(1)), null


def _parse_margin(raw: str, *, place: int | None) -> tuple[str | None, float | None]:
    """Return ``(raw_margin, numeric_margin_metres)``.

    Winners (place == 1) report an empty margin string; we record ``0.0``
    as the canonical numeric margin for consistency with par-time math.
    """
    raw_clean = _clean(raw)
    if place == 1 and not raw_clean:
        return None, 0.0
    if not raw_clean:
        return None, None
    if m := _MARGIN_NUMERIC_RE.search(raw_clean):
        try:
            return raw_clean, float(m.group(0))
        except ValueError:
            return raw_clean, None
    return raw_clean, None


def _parse_stewards(td: Node | None) -> StewardsCommentDTO | None:
    if td is None:
        return None
    span = td.css_first("span.stewardsTooltip")
    if span is None:
        text = _clean(td.text())
        if not text:
            return None
        return StewardsCommentDTO(codes=text.split(), full_text=None)

    codes_text = _clean(span.text())
    full_text = (
        span.attributes.get("data-original-title")
        or span.attributes.get("title")
        or None
    )
    return StewardsCommentDTO(
        codes=codes_text.split() if codes_text else [],
        full_text=_clean(full_text) if full_text else None,
    )


def _runner_rows(table: Node) -> Iterable[Node]:
    """Yield ``<tr>`` rows that look like runner rows.

    Skips header/spacer rows that contain no ``a.horse_name_link``.
    """
    for tr in table.css("tr"):
        if tr.css_first("a.horse_name_link") is not None:
            yield tr


def _parse_runner(tr: Node) -> RunnerDTO | None:
    horse_anchor = tr.css_first("a.horse_name_link")
    if horse_anchor is None:  # pragma: no cover — _runner_rows already filters
        return None
    href = horse_anchor.attributes.get("href", "") or ""
    horse_id_m = _HORSE_ID_RE.search(href)
    if horse_id_m is None:
        return None
    horse_id = int(horse_id_m.group(1))
    horse_name = _clean(horse_anchor.text())

    place_cells = tr.css("td.horse_number")
    place_text = _clean(place_cells[0].text()) if place_cells else ""
    finish_position, null_run = _parse_place(place_text)

    runner_number: int | None = None
    if len(place_cells) >= 2:
        rn_text = _clean(place_cells[1].text())
        if rn_text.isdigit():
            runner_number = int(rn_text)

    barrier_node = tr.css_first("td.barrier")
    barrier_raw = _clean(barrier_node.text()) if barrier_node else None
    barrier_raw = barrier_raw or None
    barrier = _barrier_to_int(barrier_raw)

    prizemoney_node = tr.css_first("td.prizemoney")
    stake = _parse_decimal(prizemoney_node.text()) if prizemoney_node else None

    margin_node = tr.css_first("td.margin")
    raw_margin, adjusted_margin = _parse_margin(
        margin_node.text() if margin_node else "", place=finish_position
    )

    starting_node = tr.css_first("td.starting_price")
    raw_price = _clean(starting_node.text()) if starting_node else None
    starting_price = _parse_decimal(raw_price or "", regex=_PRICE_RE)

    trainer_anchor = tr.css_first("td.trainer a")
    trainer_name = _clean(trainer_anchor.text()) if trainer_anchor else None
    trainer_token = _parse_link_token(
        trainer_anchor.attributes.get("href", "") if trainer_anchor else "",
        _TRAINER_LINK_RE,
    )

    driver_anchor = tr.css_first("td.driver a")
    driver_name = _clean(driver_anchor.text()) if driver_anchor else None
    driver_token = _parse_link_token(
        driver_anchor.attributes.get("href", "") if driver_anchor else "",
        _DRIVER_LINK_RE,
    )

    stewards = _parse_stewards(tr.css_first("td.stewards_comments"))

    return RunnerDTO(
        horse_id=horse_id,
        horse_name=horse_name,
        finish_position=finish_position,
        runner_number=runner_number,
        barrier_raw=barrier_raw,
        barrier=barrier,
        stake=stake,
        raw_margin=raw_margin,
        adjusted_margin=adjusted_margin,
        null_run=null_run,
        scratched=False,
        raw_price=raw_price,
        starting_price=starting_price,
        trainer_name=trainer_name,
        trainer_link_token=trainer_token,
        driver_name=driver_name,
        driver_link_token=driver_token,
        stewards=stewards,
    )


# ---------------------------------------------------------------------------
# Race times (table.raceTimes)
# ---------------------------------------------------------------------------

_RACE_TIME_FIELDS: Final = {
    "track rating": "track_rating",
    "gross time": "gross_time",
    "mile rate": "mile_rate",
    "lead time": "lead_time",
    "first quarter": "q1",
    "second quarter": "q2",
    "third quarter": "q3",
    "fourth quarter": "q4",
}
_MARGINS_RE: Final = re.compile(
    r"margins?:\s*(?P<a>[\d.]+m|[A-Z]+)\s*x\s*(?P<b>[\d.]+m|[A-Z]+)",
    re.IGNORECASE,
)

# Harness-racing shorthand margins. Approximate metres per the convention used
# by Australian harness reporting (HRA stewards' table). Used as a fallback
# when the margin isn't expressed as a numeric ``Nm`` value.
_SHORTHAND_MARGIN_M: Final[dict[str, float]] = {
    "NS": 0.05, "NOSE": 0.05,
    "SHD": 0.10, "SHHD": 0.10, "SHORTHEAD": 0.10,
    "HD": 0.15, "HEAD": 0.15,
    "SHFHD": 0.18, "SHORTHALFHEAD": 0.18,
    "HFHD": 0.20, "HALFHEAD": 0.20,
    "HFNK": 0.25, "HALFNECK": 0.25,
    "NK": 0.30, "NECK": 0.30,
    "QTRLEN": 0.45, "QUARTERLENGTH": 0.45,
    "HFLEN": 0.90, "HALFLENGTH": 0.90,
    "LEN": 1.80, "LENGTH": 1.80,
}


def _margin_token_to_m(token: str) -> float | None:
    """Convert ``"4.4m"`` / ``"NK"`` / ``"SHFHD"`` to a numeric metre value."""
    cleaned = token.strip().upper()
    if cleaned.endswith("M") and any(c.isdigit() for c in cleaned[:-1]):
        try:
            return float(cleaned[:-1])
        except ValueError:
            return None
    return _SHORTHAND_MARGIN_M.get(cleaned)


def _parse_race_times(table: Node | None) -> RaceTimesDTO | None:
    if table is None:
        return None
    data: dict = {}
    for td in table.css("td"):
        raw = _clean(td.text())
        if not raw:
            continue
        lowered = raw.lower()
        if mm := _MARGINS_RE.search(raw):
            data["margin1"] = _margin_token_to_m(mm.group("a"))
            data["margin2"] = _margin_token_to_m(mm.group("b"))
            continue
        for label, key in _RACE_TIME_FIELDS.items():
            if lowered.startswith(label):
                value = raw[len(label):].lstrip(":").strip()
                _assign_time(data, key, value)
                break
    if not data:
        return None
    return RaceTimesDTO(**data)


def _assign_time(data: dict, key: str, value: str) -> None:
    """Store both display + seconds for a time field, or the raw string for track_rating."""
    if key == "track_rating":
        data["track_rating"] = value or None
        return
    if not value:
        return
    try:
        display, seconds = to_ss_ms(value)
    except TimeParseError:
        return
    data[f"{key}_display"] = display
    data[f"{key}_s"] = seconds


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


def parse_results_html(
    html: str,
    *,
    meeting_code: str,
    state: str,
    fallback_track: str | None = None,
    fallback_date: date | None = None,
    fallback_day_night: DayNight = "UNKNOWN",
) -> MeetingDTO:
    """Parse a meeting result page into a :class:`MeetingDTO`.

    Fallbacks let the scraper pass the manifest-derived track / date / day_night
    in case the page heading is missing or unparseable. The parser prefers the
    on-page values when available.
    """
    if not html or not html.strip():
        raise MeetingParseError(f"empty HTML for meeting {meeting_code!r}")

    tree = HTMLParser(html)

    track_from_page, day_night_from_page, date_from_page = _parse_meeting_heading(tree)
    track_name = track_from_page or fallback_track
    if track_name is None:
        raise MeetingParseError(
            f"meeting heading missing and no fallback supplied for {meeting_code!r}"
        )
    day_night: DayNight = (
        day_night_from_page if day_night_from_page != "UNKNOWN" else fallback_day_night
    )
    meeting_date = date_from_page or fallback_date
    if meeting_date is None:
        raise MeetingParseError(
            f"meeting date missing and no fallback supplied for {meeting_code!r}"
        )

    headers = tree.css("table.raceMoreInfo")
    fields = tree.css("table.raceFieldTable.resultTable")
    times = tree.css("table.raceTimes")
    if not headers:
        raise MeetingParseError(f"no race headers in HTML for {meeting_code!r}")

    races: list[RaceDTO] = []
    for i, hdr in enumerate(headers):
        info = _parse_race_header(hdr)
        if info["race_number"] is None:
            continue
        cond = _split_conditions(info["conditions"])
        fld = fields[i] if i < len(fields) else None
        tm = times[i] if i < len(times) else None
        runners: list[RunnerDTO] = []
        if fld is not None:
            for tr in _runner_rows(fld):
                runner = _parse_runner(tr)
                if runner is not None:
                    runners.append(runner)
        races.append(
            RaceDTO(
                race_number=info["race_number"],
                race_name=info["race_name"],
                race_time=info["race_time"],
                distance_m=info["distance_m"],
                race_purse=cond["race_purse"],
                class_name=cond["class_name"],
                age_class=cond["age_class"],
                race_type=cond["race_type"],
                race_gait=cond["race_gait"],
                start_type=cond["start_type"],
                is_final=info["is_final"],
                times=_parse_race_times(tm),
                runners=runners,
            )
        )

    return MeetingDTO(
        meeting_code=meeting_code,
        track_name=track_name,
        state=state,
        meeting_date=meeting_date,
        day_night=day_night,
        races=races,
    )
