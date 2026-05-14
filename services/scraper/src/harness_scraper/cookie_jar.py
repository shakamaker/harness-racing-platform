"""File-backed cookie jar per session (CLAUDE.md §4.1.2).

Playwright contexts persist cookies via ``storage_state``. We pin one file
per ``session_id`` (typically ``{profile_label}-{state}``) so each scraping
session looks like a returning visitor with the prior cookies present.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CookieJarRef:
    """Pointer + helpers around a single storage-state JSON file on disk."""

    path: Path

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict[str, Any] | None:
        if not self.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupt jar — caller will re-create on next save. Surface via
            # return None so this stays a recoverable warning, not a crash.
            return None

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def delete(self) -> None:
        if self.exists():
            self.path.unlink()


def resolve_jar(directory: Path, session_id: str) -> CookieJarRef:
    """Resolve a session id to a stable per-session jar path under ``directory``."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in session_id)
    return CookieJarRef(path=directory / f"{safe}.json")
