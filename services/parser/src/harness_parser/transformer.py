"""Persist parsed :class:`MeetingDTO` objects.

Scope per Sprint 1 decision: emit JSON snapshots to ``data/parsed/{state}/
{year}/{meeting_code}.json`` so the database lane (database-architect +
sql-pro) has real ingested rows to shape the schema around. The full ORM
upsert path (CLAUDE.md §4.2.5) lands once Agent 3 publishes
``packages/models``.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_parser.dtos import MeetingDTO


def dump_meeting_json(meeting: MeetingDTO, out_dir: Path) -> Path:
    """Write ``meeting`` to ``out_dir/{state}/{year}/{meeting_code}.json``."""
    target_dir = out_dir / meeting.state / str(meeting.meeting_date.year)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / f"{meeting.meeting_code}.json"
    payload = meeting.model_dump(mode="json")
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out_path


def write_index(meetings: list[MeetingDTO], out_dir: Path) -> Path:
    """Write a compact index of parsed meetings for the DB lane to consume."""
    index_path = out_dir / "index.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    index_payload = [
        {
            "meeting_code": m.meeting_code,
            "track_name": m.track_name,
            "state": m.state,
            "meeting_date": m.meeting_date.isoformat(),
            "day_night": m.day_night,
            "race_count": len(m.races),
            "runner_count": sum(len(r.runners) for r in m.races),
        }
        for m in meetings
    ]
    index_path.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")
    return index_path


__all__ = ["dump_meeting_json", "write_index"]
