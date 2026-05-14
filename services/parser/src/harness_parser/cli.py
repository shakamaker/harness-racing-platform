"""Parser CLI: turn raw HTML files into MeetingDTO JSON.

Usage::

    python -m harness_parser.cli parse \\
        --manifest services/parser/tests/fixtures/meetings/manifest_vic_2024_01.json \\
        --out-dir data/parsed
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from harness_parser.dtos import DayNight, MeetingDTO
from harness_parser.parse import MeetingParseError, parse_results_html
from harness_parser.transformer import dump_meeting_json, write_index


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness-parser")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("parse", help="Parse meetings listed in a scraper manifest")
    pa.add_argument("--manifest", type=Path, required=True)
    pa.add_argument("--out-dir", type=Path, default=Path("data/parsed"))

    pf = sub.add_parser("parse-file", help="Parse a single raw HTML file")
    pf.add_argument("--html", type=Path, required=True)
    pf.add_argument("--meeting-code", required=True)
    pf.add_argument("--state", required=True)
    pf.add_argument("--out-dir", type=Path, default=Path("data/parsed"))
    pf.add_argument(
        "--fallback-track",
        default=None,
        help="Track name to use if the page heading is missing.",
    )
    pf.add_argument(
        "--fallback-date",
        default=None,
        help="ISO date string used if the page heading is missing.",
    )
    return p


def _cmd_parse(args: argparse.Namespace) -> int:
    manifest: list[dict] = json.loads(args.manifest.read_text(encoding="utf-8"))
    parsed: list[MeetingDTO] = []
    errors: list[dict] = []
    for entry in manifest:
        html_path = Path(entry["fixture_path"])
        if not html_path.is_file():
            html_path = Path(entry["html_path"])
        if not html_path.is_file():
            errors.append({"meeting_code": entry["meeting_code"], "error": "html_missing"})
            continue
        html = html_path.read_text(encoding="utf-8")
        try:
            meeting = parse_results_html(
                html,
                meeting_code=entry["meeting_code"],
                state=entry["state"],
                fallback_track=entry.get("track_name"),
                fallback_date=date.fromisoformat(entry["meeting_date"]),
                fallback_day_night=_normalise_day_night(entry.get("day_night", "UNKNOWN")),
            )
        except MeetingParseError as exc:
            errors.append({"meeting_code": entry["meeting_code"], "error": str(exc)})
            continue
        out = dump_meeting_json(meeting, args.out_dir)
        parsed.append(meeting)
        print(
            f"OK  {meeting.meeting_code} {meeting.track_name} "
            f"{meeting.meeting_date} races={len(meeting.races)} "
            f"runners={sum(len(r.runners) for r in meeting.races)} → {out}"
        )
    write_index(parsed, args.out_dir)
    if errors:
        print(f"\nERRORS ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  {e['meeting_code']}: {e['error']}", file=sys.stderr)
    return 0 if not errors else 1


def _cmd_parse_file(args: argparse.Namespace) -> int:
    html = args.html.read_text(encoding="utf-8")
    fallback_date = date.fromisoformat(args.fallback_date) if args.fallback_date else None
    meeting = parse_results_html(
        html,
        meeting_code=args.meeting_code,
        state=args.state,
        fallback_track=args.fallback_track,
        fallback_date=fallback_date,
    )
    out = dump_meeting_json(meeting, args.out_dir)
    print(
        f"OK  {meeting.meeting_code} {meeting.track_name} "
        f"{meeting.meeting_date} races={len(meeting.races)} "
        f"runners={sum(len(r.runners) for r in meeting.races)} → {out}"
    )
    return 0


def _normalise_day_night(value: str) -> DayNight:
    upper = value.upper()
    if upper in ("DAY", "NIGHT", "TWILIGHT"):
        return upper  # type: ignore[return-value]
    return "UNKNOWN"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "parse":
        return _cmd_parse(args)
    if args.cmd == "parse-file":
        return _cmd_parse_file(args)
    parser.error(f"unknown command {args.cmd}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
