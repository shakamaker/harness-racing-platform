"""Metadata sanity tests — the mv_par_times view skips create/drop, and the
parser DTO keeps its half-time fields as computed_fields rather than columns.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_parser_on_path() -> None:
    parser_src = (
        Path(__file__).resolve().parents[3] / "services" / "parser" / "src"
    )
    if parser_src.is_dir() and str(parser_src) not in sys.path:
        sys.path.insert(0, str(parser_src))


_ensure_parser_on_path()

import harness_models  # noqa: E402  (sys.path bootstrap above is intentional)
from harness_models import Base, mv_par_times_table  # noqa: E402


class TestMvParTimesIsRegisteredButGuarded:
    def test_table_is_in_metadata(self) -> None:
        assert "mv_par_times" in Base.metadata.tables

    def test_before_create_listener_returns_false(self) -> None:
        from sqlalchemy import event

        # Walk the registered before_create listeners on the Table and confirm
        # at least one returns False (our skip-guard).
        listeners = event.contains(mv_par_times_table, "before_create", lambda *a, **k: None)
        # `contains` only checks for a SPECIFIC listener; instead, just call
        # the dispatch and confirm no exception + that at least one listener
        # exists by walking the descriptor.
        descriptor = mv_par_times_table.dispatch.before_create
        callbacks = [c for c in descriptor]
        assert callbacks, "expected before_create listener on mv_par_times"
        # Verify that at least one returns False (skip-create marker).
        results = [cb(mv_par_times_table, None) for cb in callbacks]
        assert any(r is False for r in results)
        del listeners  # silence "unused" lint

    def test_before_drop_listener_returns_false(self) -> None:
        descriptor = mv_par_times_table.dispatch.before_drop
        callbacks = [c for c in descriptor]
        assert callbacks, "expected before_drop listener on mv_par_times"
        results = [cb(mv_par_times_table, None) for cb in callbacks]
        assert any(r is False for r in results)


class TestParserRaceTimesDtoHalves:
    def test_halves_are_computed_fields(self) -> None:
        from harness_parser.dtos import RaceTimesDTO

        computed_keys = set(RaceTimesDTO.model_computed_fields.keys())
        assert "first_half_s" in computed_keys
        assert "second_half_s" in computed_keys
        # And NOT regular model fields.
        regular_keys = set(RaceTimesDTO.model_fields.keys())
        assert "first_half_s" not in regular_keys
        assert "second_half_s" not in regular_keys


class TestPackagePublicAPI:
    def test_mv_par_times_class_is_dropped(self) -> None:
        # MvParTimes was removed (item 2). Importing it must fail.
        assert not hasattr(harness_models, "MvParTimes")
