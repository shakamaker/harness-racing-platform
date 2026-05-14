"""Fixture-driven tests for ``parse_results_html`` against captured live HTML."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from harness_parser import MeetingDTO, parse_results_html
from harness_parser.transformer import dump_meeting_json

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "meetings"
MANIFEST = FIXTURE_DIR / "manifest_vic_2024_01.json"


pytestmark = pytest.mark.skipif(
    not MANIFEST.is_file(),
    reason=(
        "Live meeting fixtures missing. Run "
        "`python -m harness_scraper.cli fixtures --state vic --year 2024 --month 1` "
        "to capture them."
    ),
)


def _load_fixture(meeting_code: str) -> tuple[str, dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next(e for e in manifest if e["meeting_code"] == meeting_code)
    html_path = FIXTURE_DIR / f"meeting_vic_{meeting_code}.html"
    return html_path.read_text(encoding="utf-8"), entry


@pytest.fixture
def geelong_meeting() -> MeetingDTO:
    html, entry = _load_fixture("GE310124")
    return parse_results_html(
        html,
        meeting_code="GE310124",
        state="vic",
        fallback_track=entry["track_name"],
        fallback_date=date.fromisoformat(entry["meeting_date"]),
    )


class TestMeetingShape:
    def test_meeting_metadata(self, geelong_meeting: MeetingDTO) -> None:
        m = geelong_meeting
        assert m.meeting_code == "GE310124"
        assert m.track_name == "Geelong"
        assert m.state == "vic"
        assert m.meeting_date == date(2024, 1, 31)
        assert m.day_night == "NIGHT"

    def test_race_count(self, geelong_meeting: MeetingDTO) -> None:
        assert len(geelong_meeting.races) == 10

    def test_runner_total(self, geelong_meeting: MeetingDTO) -> None:
        total = sum(len(r.runners) for r in geelong_meeting.races)
        assert total >= 80


class TestRaceFields:
    def test_race_one_header(self, geelong_meeting: MeetingDTO) -> None:
        r = geelong_meeting.races[0]
        assert r.race_number == 1
        assert r.race_name == "HARAS DES TROTTEURS TROT (1ST HEAT)"
        assert r.distance_m == 2100
        assert r.race_purse == 4500.0
        assert r.race_gait == "TROTTERS"
        assert r.start_type == "Mobile"
        assert r.is_final is True

    def test_all_races_have_gait_and_start_type(self, geelong_meeting: MeetingDTO) -> None:
        for r in geelong_meeting.races:
            assert r.race_gait is not None, f"race {r.race_number} missing gait"
            assert r.start_type is not None, f"race {r.race_number} missing start_type"

    def test_all_races_have_purse(self, geelong_meeting: MeetingDTO) -> None:
        for r in geelong_meeting.races:
            assert r.race_purse is not None, f"race {r.race_number} missing purse"


class TestRaceTimes:
    def test_race_one_gross_and_mile_rate(self, geelong_meeting: MeetingDTO) -> None:
        t = geelong_meeting.races[0].times
        assert t is not None
        assert t.track_rating == "GOOD"
        assert t.gross_time_display == "161:700"
        assert t.gross_time_s == 161.7
        assert t.mile_rate_display == "123:900"
        assert t.mile_rate_s == 123.9
        assert t.lead_time_s == 36.6
        assert t.q1_s == 33.1 and t.q2_s == 32.1
        assert t.q3_s == 29.6 and t.q4_s == 30.3

    def test_margins_extracted(self, geelong_meeting: MeetingDTO) -> None:
        t = geelong_meeting.races[0].times
        assert t is not None and t.margin1 == 4.4 and t.margin2 == 3.6

    def test_halves_calculated_from_quarters(self, geelong_meeting: MeetingDTO) -> None:
        # Per project issue #5: first_half_s = q1+q2, second_half_s = q3+q4.
        t = geelong_meeting.races[0].times
        assert t is not None
        assert t.first_half_s == round(33.1 + 32.1, 3)
        assert t.second_half_s == round(29.6 + 30.3, 3)

    def test_display_fields_for_halves_dropped(
        self, geelong_meeting: MeetingDTO
    ) -> None:
        # Per project issue #4: first_half_display / last_half_display removed.
        t = geelong_meeting.races[0].times
        assert t is not None
        # Pydantic v2 forbids extra fields; this fails loudly if they crept back.
        assert "first_half_display" not in t.model_dump()
        assert "last_half_display" not in t.model_dump()
        assert "last_half_s" not in t.model_dump()

    def test_all_races_have_gross_time(self, geelong_meeting: MeetingDTO) -> None:
        for r in geelong_meeting.races:
            assert r.times is not None
            assert r.times.gross_time_s is not None, (
                f"race {r.race_number} missing gross_time"
            )


class TestRunnerFields:
    def test_winner_of_race_one(self, geelong_meeting: MeetingDTO) -> None:
        winner = next(
            r for r in geelong_meeting.races[0].runners if r.finish_position == 1
        )
        assert winner.horse_name == "ROCKFORD PEACH"
        assert winner.horse_id == 800955
        assert winner.barrier_raw == "Fr7"
        assert winner.barrier == 7
        assert winner.starting_price == 3.0
        assert winner.stake == 2250.0
        assert winner.adjusted_margin == 0.0
        assert winner.trainer_name == "Lisa Miles"
        assert winner.trainer_link_token is not None
        assert winner.driver_name == "Lisa Miles"
        assert winner.driver_link_token is not None

    def test_stewards_comments(self, geelong_meeting: MeetingDTO) -> None:
        winner = next(
            r for r in geelong_meeting.races[0].runners if r.finish_position == 1
        )
        assert winner.stewards is not None
        assert "HISU" in winner.stewards.codes
        assert "hung in score up" in (winner.stewards.full_text or "").lower()

    def test_all_runners_have_horse_id(self, geelong_meeting: MeetingDTO) -> None:
        for race in geelong_meeting.races:
            for runner in race.runners:
                assert runner.horse_id > 0

    def test_barrier_raw_and_barrier_int_split(self, geelong_meeting: MeetingDTO) -> None:
        # Per project issue #6: barrier_raw keeps "Fr7"; barrier holds int 7.
        for race in geelong_meeting.races:
            for runner in race.runners:
                if runner.barrier_raw is None:
                    assert runner.barrier is None
                    continue
                if any(c.isdigit() for c in runner.barrier_raw):
                    assert runner.barrier is not None, (
                        f"barrier_raw={runner.barrier_raw!r} has digits but "
                        f"barrier was None for {runner.horse_name}"
                    )

    def test_stewards_has_no_adjustment_value_field(
        self, geelong_meeting: MeetingDTO
    ) -> None:
        # Per project issue #7: adjustment_value removed entirely.
        winner = next(
            r for r in geelong_meeting.races[0].runners if r.finish_position == 1
        )
        assert winner.stewards is not None
        assert "adjustment_value" not in winner.stewards.model_dump()

    def test_all_runners_have_starting_price(self, geelong_meeting: MeetingDTO) -> None:
        misses: list[str] = []
        for race in geelong_meeting.races:
            for runner in race.runners:
                if runner.starting_price is None:
                    misses.append(f"R{race.race_number} {runner.horse_name}")
        assert not misses, f"runners missing starting_price: {misses}"


class TestTransformerRoundtrip:
    def test_dump_writes_json(
        self, geelong_meeting: MeetingDTO, tmp_path: Path
    ) -> None:
        out_path = dump_meeting_json(geelong_meeting, tmp_path)
        assert out_path.is_file()
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["meeting_code"] == "GE310124"
        assert payload["races"][0]["race_number"] == 1


class TestErrorPaths:
    def test_empty_html_raises(self) -> None:
        from harness_parser.parse import MeetingParseError

        with pytest.raises(MeetingParseError):
            parse_results_html("", meeting_code="X", state="vic")

    def test_missing_heading_with_no_fallback(self) -> None:
        from harness_parser.parse import MeetingParseError

        with pytest.raises(MeetingParseError):
            parse_results_html(
                "<html><body>no header</body></html>",
                meeting_code="X",
                state="vic",
            )
