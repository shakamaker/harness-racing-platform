"""Schema contract tests — happy paths, extra=forbid, validators, quantisers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from harness_models.meetings import DayNight, MeetingStatus
from harness_models.schemas import (
    HorseUpsert,
    MeetingCreate,
    PersonUpsert,
    RaceCreate,
    RaceTimeCreate,
    RunnerCreate,
    StewardsCommentUpsert,
    TrackCreate,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class TestHappyPaths:
    def test_meeting_create(self) -> None:
        m = MeetingCreate(
            meeting_code="GE310124",
            track_id=1,
            meeting_date=date(2024, 1, 31),
            day_night=DayNight.NIGHT,
        )
        assert m.meeting_code == "GE310124"
        assert m.status == MeetingStatus.PENDING_DOWNLOAD

    def test_track_create(self) -> None:
        TrackCreate(track_name="Geelong", state_id=1)

    def test_person_upsert(self) -> None:
        PersonUpsert(name="Lisa Miles", link_token="lisa-miles")

    def test_horse_upsert(self) -> None:
        HorseUpsert(horse_id=800955, horse_name="Rockford Peach")

    def test_race_create(self) -> None:
        RaceCreate(meeting_id=1, race_number=1, distance_m=2100)

    def test_race_time_create(self) -> None:
        RaceTimeCreate(race_id=1, gross_time_s=Decimal("161.7"))

    def test_runner_create(self) -> None:
        RunnerCreate(race_id=1, horse_id=800955)

    def test_stewards_comment_default_codes_is_fresh_list(self) -> None:
        a = StewardsCommentUpsert(runner_id=1)
        b = StewardsCommentUpsert(runner_id=2)
        a.code_ids.append(7)
        # The previous `= []` default leaked across instances; the new
        # default_factory=list must not.
        assert b.code_ids == []


class TestExtraForbid:
    def test_meeting_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            MeetingCreate(  # type: ignore[call-arg]
                meeting_code="X",
                track_id=1,
                meeting_date=date(2024, 1, 1),
                bogus="oops",
            )

    def test_runner_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            RunnerCreate(  # type: ignore[call-arg]
                race_id=1,
                horse_id=1,
                bogus="oops",
            )


class TestBarrierConsistency:
    def test_matching_pair_succeeds(self) -> None:
        r = RunnerCreate(race_id=1, horse_id=1, barrier=5, barrier_raw="Fr5")
        assert r.barrier == 5

    def test_mismatching_pair_fails(self) -> None:
        with pytest.raises(ValidationError):
            RunnerCreate(race_id=1, horse_id=1, barrier=5, barrier_raw="Fr9")

    def test_only_one_side_set_is_allowed(self) -> None:
        # If only barrier is set, no consistency check fires.
        RunnerCreate(race_id=1, horse_id=1, barrier=5)
        RunnerCreate(race_id=1, horse_id=1, barrier_raw="Fr5")


class TestMoneyQuantising:
    def test_stake_rounds_to_two_dp(self) -> None:
        r = RunnerCreate(
            race_id=1, horse_id=1, stake=Decimal("1.234")
        )
        # Decimal quantise default rounding: ROUND_HALF_EVEN -> 1.23.
        assert r.stake == Decimal("1.23")

    def test_starting_price_rounds_to_two_dp(self) -> None:
        r = RunnerCreate(
            race_id=1, horse_id=1, starting_price=Decimal("3.499")
        )
        assert r.starting_price == Decimal("3.50")

    def test_race_purse_rounds_to_two_dp(self) -> None:
        r = RaceCreate(meeting_id=1, race_number=1, race_purse=Decimal("4500.005"))
        # ROUND_HALF_EVEN on 4500.005 -> 4500.00.
        assert r.race_purse == Decimal("4500.00")

    def test_time_quantises_to_three_dp(self) -> None:
        t = RaceTimeCreate(race_id=1, gross_time_s=Decimal("161.7"))
        assert t.gross_time_s == Decimal("161.700")
