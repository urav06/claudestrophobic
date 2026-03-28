#!/usr/bin/env python3
""" Maps Claude Code chat names to UUIDs for the current project. """

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR  = Path.home() / ".claude"
HISTORY     = CLAUDE_DIR / "history.jsonl"
PROJECTS    = CLAUDE_DIR / "projects"


@dataclass
class Session:
    uuid            : str
    timestamp       : int           = 0
    name            : str | None    = None
    first_message   : str | None    = None

    @property
    def display_name(self) -> str:
        return self.name or self.first_message or "(unnamed)"

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    def file_size(self, base: Path) -> str:
        try:
            n = (base / f"{self.uuid}.jsonl").stat().st_size
        except OSError:
            return "?"
        return f"{n / 1_048_576:.1f}M" if n >= 1_048_576 else f"{n / 1024:.0f}K"


# ── Parse history.jsonl into one Session per chat ────────────────


def parse_sessions(project: str) -> list[Session]:
    if not HISTORY.exists():
        return []

    sessions: dict[str, Session] = {}
    for line in filter(str.strip, HISTORY.read_text().splitlines()):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid, display = entry.get("sessionId"), entry.get("display", "")
        if not sid or entry.get("project") != project:
            continue

        s = sessions.setdefault(sid, Session(uuid=sid, timestamp=entry.get("timestamp", 0)))
        if display.startswith("/rename "):
            s.name = display.removeprefix("/rename ")
        elif not display.startswith("/") and len(display) > 3 and not s.first_message:
            s.first_message = display[:80]

    return sorted(sessions.values(), key=lambda s: s.timestamp, reverse=True)


def _session_id(line: str) -> str | None:
    try:
        return json.loads(line).get("sessionId")
    except (json.JSONDecodeError, ValueError):
        return None


# ── Actions ──────────────────────────────────────────────────────


def purge_session(uuid: str):
    """Remove all history entries for a session UUID."""
    lines = HISTORY.read_text().splitlines()
    lines = [l for l in lines if _session_id(l) != uuid]
    HISTORY.write_text("\n".join(lines) + "\n")


def print_table(project: str):
    sessions = parse_sessions(project)
    if not sessions:
        print("NO_SESSIONS")
        sys.exit(0)

    project_dir = PROJECTS / project.replace("/", "-")
    print("name | uuid | date | size")
    print("---- | ---- | ---- | ----")
    for s in sessions:
        print(f"{s.display_name} | {s.uuid} | {s.date} | {s.file_size(project_dir)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--purge"]:
        purge_session(args[1])
    elif args:
        print_table(args[0])
    else:
        print_table(str(Path.cwd()))
