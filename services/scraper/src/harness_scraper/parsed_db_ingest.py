"""Parser → DB ingest (CLAUDE.md §4.2.5).

Reads downloaded meeting HTML, runs it through ``harness_parser``, and upserts
the resulting MeetingDTO into ``races``, ``race_times``, ``runners``,
``horses``, ``persons``, and ``stewards_comments`` via the ``harness_models``
ORM. Idempotency keys per spec:

  * races       — (meeting_id, race_number)
  * runners     — (race_id, horse_id)
  * race_times  — race_id (PK)
  * horses      — horse_id (source-system id, PK)
  * persons     — link_token (unique); name-derived fallback when missing
  * stewards    — runner_id (PK)

Lookup tables (race_gaits, start_types, race_classes, age_classes,
race_types, horse_sexes) are populated on-demand: an unseen value gets
upserted, then cached for the rest of the run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from harness_models import (
    AgeClass,
    Horse,
    MeetingStatus,
    Person,
    Race,
    RaceClass,
    RaceGait,
    RaceMeeting,
    RaceTime,
    RaceType,
    Runner,
    StartType,
    StewardsComment,
)
from harness_parser.dtos import MeetingDTO, RaceDTO, RunnerDTO
from harness_parser.parse import MeetingParseError, parse_results_html


def _sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    norm = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return _SLUG_RE.sub("-", norm.lower()).strip("-")


def _dec(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


# adjusted_margin column is Numeric(6,3) — max abs value < 1000.
# Anything ≥ 1000L is a parser false-positive (race codes / placeholders that
# matched the bare-number regex), not a real margin.
_MARGIN_MAX = Decimal("999.999")


def _clamp_margin(value: float | None) -> Decimal | None:
    d = _dec(value)
    if d is None:
        return None
    if abs(d) > _MARGIN_MAX:
        return None
    return d


class LookupCache:
    """Lazy-upsert lookup tables. One instance per ingest run."""

    def __init__(self, session: Session) -> None:
        self._s = session
        self._cache: dict[tuple[type, str], int] = {}

    def _get_or_create(self, model: type, *, name_field: str, value: str) -> int:
        key = (model, value)
        if key in self._cache:
            return self._cache[key]
        column = getattr(model, name_field)
        existing = self._s.execute(
            select(model).where(column == value)
        ).scalar_one_or_none()
        if existing is not None:
            self._cache[key] = existing.id
            return existing.id
        row = model(**{name_field: value})
        self._s.add(row)
        self._s.flush()
        self._cache[key] = row.id
        return row.id

    def race_gait(self, name: str | None) -> int | None:
        if not name:
            return None
        return self._get_or_create(RaceGait, name_field="name", value=name.strip())

    def start_type(self, name: str | None) -> int | None:
        if not name:
            return None
        return self._get_or_create(StartType, name_field="name", value=name.strip())

    def race_class(self, name: str | None) -> int | None:
        if not name:
            return None
        return self._get_or_create(RaceClass, name_field="name", value=name.strip())

    def age_class(self, name: str | None) -> int | None:
        if not name:
            return None
        return self._get_or_create(AgeClass, name_field="name", value=name.strip())

    def race_type(self, name: str | None) -> int | None:
        if not name:
            return None
        return self._get_or_create(RaceType, name_field="name", value=name.strip())


def _upsert_horse(session: Session, *, horse_id: int, horse_name: str) -> None:
    stmt = (
        pg_insert(Horse)
        .values(horse_id=horse_id, horse_name=horse_name)
        .on_conflict_do_update(
            index_elements=[Horse.horse_id],
            set_={"horse_name": horse_name},
        )
    )
    session.execute(stmt)


def _upsert_person(session: Session, *, name: str, link_token: str | None) -> int:
    """Upsert a Person and return its id. ``link_token`` falls back to a
    name-derived slug if the source HTML didn't include one (older meetings)."""
    token = (link_token or "").strip() or f"name:{_slugify(name)}"
    existing = session.execute(
        select(Person).where(Person.link_token == token)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.name != name:
            existing.name = name
        return existing.id
    p = Person(name=name, link_token=token)
    session.add(p)
    session.flush()
    return p.id


def _upsert_race(session: Session, *, meeting_id: int, dto: RaceDTO, cache: LookupCache) -> int:
    """Upsert one race; return its id."""
    existing = session.execute(
        select(Race).where(
            Race.meeting_id == meeting_id, Race.race_number == dto.race_number
        )
    ).scalar_one_or_none()
    values: dict[str, Any] = {
        "meeting_id": meeting_id,
        "race_number": dto.race_number,
        "race_name": dto.race_name,
        "distance_m": dto.distance_m,
        "race_type_id": cache.race_type(dto.race_type),
        "race_gait_id": cache.race_gait(dto.race_gait),
        "start_type_id": cache.start_type(dto.start_type),
        "race_class_id": cache.race_class(dto.class_name),
        "age_class_id": cache.age_class(dto.age_class),
        "race_purse": _dec(dto.race_purse),
        "race_time_str": dto.race_time,
        "is_final": dto.is_final,
    }
    if existing is None:
        race = Race(**values)
        session.add(race)
        session.flush()
        return race.id
    for k, v in values.items():
        setattr(existing, k, v)
    session.flush()
    return existing.id


def _upsert_race_times(session: Session, *, race_id: int, dto: RaceDTO) -> None:
    if dto.times is None:
        return
    t = dto.times
    values = {
        "race_id": race_id,
        "gross_time_s": _dec(t.gross_time_s),
        "lead_time_s": _dec(t.lead_time_s),
        "mile_rate_s": _dec(t.mile_rate_s),
        "q1_s": _dec(t.q1_s),
        "q2_s": _dec(t.q2_s),
        "q3_s": _dec(t.q3_s),
        "q4_s": _dec(t.q4_s),
        "margin1": _dec(t.margin1),
        "margin2": _dec(t.margin2),
    }
    if all(v is None for k, v in values.items() if k != "race_id"):
        return
    stmt = (
        pg_insert(RaceTime)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[RaceTime.race_id],
            set_={k: v for k, v in values.items() if k != "race_id"},
        )
    )
    session.execute(stmt)


def _upsert_runner(
    session: Session, *, race_id: int, runner: RunnerDTO
) -> int:
    _upsert_horse(session, horse_id=runner.horse_id, horse_name=runner.horse_name)
    trainer_id = (
        _upsert_person(
            session, name=runner.trainer_name, link_token=runner.trainer_link_token
        )
        if runner.trainer_name
        else None
    )
    driver_id = (
        _upsert_person(
            session, name=runner.driver_name, link_token=runner.driver_link_token
        )
        if runner.driver_name
        else None
    )

    existing = session.execute(
        select(Runner).where(
            Runner.race_id == race_id, Runner.horse_id == runner.horse_id
        )
    ).scalar_one_or_none()
    values: dict[str, Any] = {
        "race_id": race_id,
        "horse_id": runner.horse_id,
        "runner_number": runner.runner_number,
        "barrier": runner.barrier,
        "barrier_raw": runner.barrier_raw,
        "trainer_id": trainer_id,
        "driver_id": driver_id,
        "finish_position": runner.finish_position,
        "raw_margin": runner.raw_margin,
        "adjusted_margin": _clamp_margin(runner.adjusted_margin),
        "null_run": runner.null_run,
        "scratched": runner.scratched,
        "stake": _dec(runner.stake),
        "raw_price": runner.raw_price,
        "starting_price": _dec(runner.starting_price),
    }
    if existing is None:
        r = Runner(**values)
        session.add(r)
        session.flush()
        runner_id = r.id
    else:
        for k, v in values.items():
            setattr(existing, k, v)
        session.flush()
        runner_id = existing.id

    if runner.stewards and (runner.stewards.full_text or runner.stewards.codes):
        sc = session.get(StewardsComment, runner_id)
        if sc is None:
            sc = StewardsComment(runner_id=runner_id, full_text=runner.stewards.full_text)
            session.add(sc)
        else:
            sc.full_text = runner.stewards.full_text
        session.flush()
    return runner_id


def ingest_meeting(
    session: Session,
    *,
    meeting: MeetingDTO,
    cache: LookupCache,
) -> dict[str, int]:
    """Upsert one parsed meeting. Returns per-meeting counts."""
    row = session.execute(
        select(RaceMeeting).where(RaceMeeting.meeting_code == meeting.meeting_code)
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(
            f"race_meetings has no row for {meeting.meeting_code!r}. "
            "Run db_ingest (calendar→DB) first."
        )

    counts = {"races": 0, "runners": 0, "race_times": 0, "runners_skipped": 0}
    for race_dto in meeting.races:
        race_id = _upsert_race(session, meeting_id=row.id, dto=race_dto, cache=cache)
        counts["races"] += 1
        _upsert_race_times(session, race_id=race_id, dto=race_dto)
        if race_dto.times is not None:
            counts["race_times"] += 1
        for runner in race_dto.runners:
            # Savepoint per runner so DataError on one row doesn't poison the
            # transaction holding the rest of the meeting.
            sp = session.begin_nested()
            try:
                _upsert_runner(session, race_id=race_id, runner=runner)
                sp.commit()
                counts["runners"] += 1
            except Exception as exc:  # noqa: BLE001 — we log and skip
                sp.rollback()
                counts["runners_skipped"] += 1
                print(
                    f"  WARN  {meeting.meeting_code} race={race_dto.race_number} "
                    f"horse_id={runner.horse_id}: skip runner ({type(exc).__name__}: {exc})",
                    flush=True,
                )

    row.status = MeetingStatus.PARSED
    session.flush()
    return counts


def iter_downloaded_meetings(
    session: Session, *, state_code: str, year_start: int, year_end: int
) -> list[tuple[str, Path]]:
    """Return (meeting_code, html_path) for every DOWNLOADED meeting in range."""
    from datetime import date

    rows = session.execute(
        select(RaceMeeting.meeting_code, RaceMeeting.html_path)
        .where(
            RaceMeeting.status == MeetingStatus.DOWNLOADED,
            RaceMeeting.meeting_date >= date(year_start, 1, 1),
            RaceMeeting.meeting_date <= date(year_end, 12, 31),
        )
        .order_by(RaceMeeting.meeting_date)
    ).all()
    out: list[tuple[str, Path]] = []
    for meeting_code, html_path in rows:
        if not html_path:
            continue
        p = Path(html_path)
        if p.is_file():
            out.append((meeting_code, p))
    return out


def _parse_one(
    html: str,
    *,
    meeting_code: str,
    state: str,
    fallback_track: str | None,
    fallback_date,
    fallback_day_night: str = "UNKNOWN",
) -> MeetingDTO:
    return parse_results_html(
        html,
        meeting_code=meeting_code,
        state=state,
        fallback_track=fallback_track,
        fallback_date=fallback_date,
        fallback_day_night=fallback_day_night,  # type: ignore[arg-type]
    )


def run_parsed_ingest(
    *,
    engine: Engine,
    state: str,
    year_start: int,
    year_end: int,
    limit: int | None = None,
) -> dict:
    totals = {
        "meetings_attempted": 0,
        "meetings_parsed": 0,
        "meetings_failed": 0,
        "races": 0,
        "runners": 0,
        "race_times": 0,
    }
    failures: list[dict] = []
    per_track: dict[str, int] = defaultdict(int)

    with Session(engine, future=True) as session:
        targets = iter_downloaded_meetings(
            session, state_code=state, year_start=year_start, year_end=year_end
        )
        if limit is not None:
            targets = targets[:limit]

        cache = LookupCache(session)
        for i, (meeting_code, html_path) in enumerate(targets, 1):
            totals["meetings_attempted"] += 1
            row = session.execute(
                select(RaceMeeting).where(RaceMeeting.meeting_code == meeting_code)
            ).scalar_one()
            try:
                html = html_path.read_text(encoding="utf-8")
                meeting = _parse_one(
                    html,
                    meeting_code=meeting_code,
                    state=state.lower(),
                    fallback_track=row.track.track_name if row.track else None,
                    fallback_date=row.meeting_date,
                    fallback_day_night=str(row.day_night.value),
                )
                counts = ingest_meeting(session, meeting=meeting, cache=cache)
                session.commit()
                totals["meetings_parsed"] += 1
                totals["races"] += counts["races"]
                totals["runners"] += counts["runners"]
                totals["race_times"] += counts["race_times"]
                totals["runners_skipped"] = totals.get("runners_skipped", 0) + counts.get(
                    "runners_skipped", 0
                )
                per_track[meeting.track_name] += counts["races"]
                if i % 25 == 0 or i == len(targets):
                    print(
                        f"[{i}/{len(targets)}] {meeting_code} {meeting.track_name} "
                        f"races={counts['races']} runners={counts['runners']}",
                        flush=True,
                    )
            except (MeetingParseError, ValueError, OSError) as exc:
                session.rollback()
                totals["meetings_failed"] += 1
                failures.append({"meeting_code": meeting_code, "error": str(exc)})
                print(f"[{i}/{len(targets)}] {meeting_code} FAILED: {exc}", flush=True)

    return {
        "totals": totals,
        "top_tracks_by_races": dict(
            sorted(per_track.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ),
        "failures_sample": failures[:10],
        "failure_count": len(failures),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-parsed-db-ingest")
    parser.add_argument("--state", required=True)
    parser.add_argument("--year-start", type=int, required=True)
    parser.add_argument("--year-end", type=int, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or $DATABASE_URL is required")

    engine = create_engine(_sync_url(args.database_url), future=True)
    report = run_parsed_ingest(
        engine=engine,
        state=args.state,
        year_start=args.year_start,
        year_end=args.year_end,
        limit=args.limit,
    )
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report["totals"]["meetings_failed"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
