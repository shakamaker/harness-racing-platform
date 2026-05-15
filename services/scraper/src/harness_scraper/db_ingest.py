"""Pump calendar manifests into Postgres via the harness_models ORM.

For each meeting row discovered by the calendar scrape (CLAUDE.md §4.1.3):
  * upsert a ``race_tracks`` row keyed on ``(track_name, state_id)``
  * upsert a ``race_meetings`` row keyed on ``meeting_code``, with
    ``status=PENDING_DOWNLOAD`` (or ``DOWNLOADED`` if raw HTML is on disk)

Intentionally minimal — this is the calendar→DB handshake described in the
project memory: prove the 3NF schema accepts real ingested rows so the DB
lane can sign off on the recent ORM/migration changes.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import cast

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from harness_models import (
    DayNight,
    MeetingStatus,
    RaceMeeting,
    RaceTrack,
    State,
)


def _sync_url(url: str) -> str:
    """Translate an async DATABASE_URL to the matching sync driver URL."""
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _resolve_state_id(session: Session, code: str) -> int:
    code_u = code.upper()
    row = session.execute(select(State).where(State.code == code_u)).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"State code {code_u!r} not seeded in `states` table.")
    return row.id


def _upsert_track(session: Session, *, track_name: str, state_id: int) -> int:
    existing = session.execute(
        select(RaceTrack).where(
            RaceTrack.track_name == track_name, RaceTrack.state_id == state_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing.id
    track = RaceTrack(track_name=track_name, state_id=state_id)
    session.add(track)
    session.flush()
    return track.id


def ingest_year(
    session: Session,
    *,
    state_code: str,
    year: int,
    manifest_path: Path,
    raw_dir: Path,
) -> dict[str, int]:
    """Upsert every meeting row in one year manifest. Idempotent."""
    state_id = _resolve_state_id(session, state_code)
    rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    counters = {"meetings_seen": 0, "meetings_upserted": 0, "tracks_upserted": 0}

    track_cache: dict[str, int] = {}
    state_lower = state_code.lower()
    raw_year_dir = raw_dir / state_lower / str(year)

    for row in rows:
        counters["meetings_seen"] += 1
        track_name = row["track_name"]
        meeting_code = row["meeting_code"]
        meeting_date = date.fromisoformat(row["meeting_date"])
        day_night = row.get("day_night", "UNKNOWN")
        meeting_href = row.get("meeting_href", "")

        if track_name not in track_cache:
            before = session.execute(
                select(RaceTrack.id).where(
                    RaceTrack.track_name == track_name, RaceTrack.state_id == state_id
                )
            ).scalar_one_or_none()
            track_cache[track_name] = _upsert_track(
                session, track_name=track_name, state_id=state_id
            )
            if before is None:
                counters["tracks_upserted"] += 1
        track_id = track_cache[track_name]

        html_path: str | None = None
        status = MeetingStatus.PENDING_DOWNLOAD
        candidate = raw_year_dir / f"{meeting_code}.html"
        if candidate.exists():
            html_path = str(candidate)
            status = MeetingStatus.DOWNLOADED

        stmt = (
            pg_insert(RaceMeeting)
            .values(
                meeting_code=meeting_code,
                track_id=track_id,
                meeting_date=meeting_date,
                day_night=DayNight(day_night),
                meeting_url=meeting_href or None,
                html_path=html_path,
                status=status,
                scraped_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=[RaceMeeting.meeting_code],
                set_={
                    "track_id": track_id,
                    "meeting_date": meeting_date,
                    "day_night": DayNight(day_night),
                    "meeting_url": meeting_href or None,
                    "html_path": html_path,
                    "status": status,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        )
        session.execute(stmt)
        counters["meetings_upserted"] += 1

    session.commit()
    return counters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-scraper-ingest")
    parser.add_argument("--state", required=True, help="State code (e.g. vic, nsw).")
    parser.add_argument("--year-start", type=int, required=True)
    parser.add_argument("--year-end", type=int, required=True)
    parser.add_argument(
        "--data-dir", type=Path, default=Path("./data"), help="Where calendar manifests live."
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=Path("./raw_html"), help="Where per-meeting HTML lives."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="SQLAlchemy URL (psycopg sync). Defaults to $DATABASE_URL.",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        parser.error("--database-url or $DATABASE_URL is required")

    engine = create_engine(_sync_url(args.database_url), future=True)
    state_lower = args.state.lower()

    overall = {"meetings_seen": 0, "meetings_upserted": 0, "tracks_upserted": 0, "years": 0}
    per_year: dict[int, dict[str, int]] = {}
    with Session(engine, future=True) as session:
        for year in range(args.year_start, args.year_end + 1):
            manifest = args.data_dir / "calendar" / state_lower / f"{year}.json"
            if not manifest.is_file():
                continue
            stats = ingest_year(
                session,
                state_code=args.state,
                year=year,
                manifest_path=manifest,
                raw_dir=args.raw_dir,
            )
            per_year[year] = stats
            overall["meetings_seen"] += stats["meetings_seen"]
            overall["meetings_upserted"] += stats["meetings_upserted"]
            overall["tracks_upserted"] += stats["tracks_upserted"]
            overall["years"] += 1

    report = {
        "state": args.state,
        "year_start": args.year_start,
        "year_end": args.year_end,
        "overall": overall,
        "per_year": {str(y): v for y, v in sorted(per_year.items())},
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
