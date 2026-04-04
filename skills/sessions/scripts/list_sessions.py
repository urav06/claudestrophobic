#!/usr/bin/env python3
"""List and manage Claude Code sessions for the current project."""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude"


# ---------------------------------------------------------------------------
#  Path encoding — mirrors Claude Code's KX() function
# ---------------------------------------------------------------------------

def project_dir(project: str) -> Path | None:

    encoded = re.sub(r"[^a-zA-Z0-9]", "-", project)
    base    = CLAUDE_DIR / "projects"
    direct  = base / encoded

    if direct.is_dir():
        return direct
    if len(encoded) > 200 and base.is_dir():
        return next((d for d in base.iterdir() if d.is_dir() and d.name.startswith(encoded[:200])), None)
    return None


# ---------------------------------------------------------------------------
#  History — first user prompt per session from history.jsonl
# ---------------------------------------------------------------------------

def _index_first_prompts(project: str) -> dict:
    history = CLAUDE_DIR / "history.jsonl"
    if not history.exists():
        return {}

    index = {}
    for line in history.open():
        try:    entry = json.loads(line)
        except json.JSONDecodeError: continue
        if entry.get("project") != project: continue

        sid     = entry.get("sessionId")
        display = entry.get("display", "")
        if isinstance(display, dict): display = display.get("display", "")

        if sid and sid not in index and isinstance(display, str) and not display.startswith("/"):
            index[sid] = " ".join(display.split())[:80]

    return index


# ---------------------------------------------------------------------------
#  Session
# ---------------------------------------------------------------------------

def _format_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024: return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _active_session_ids() -> set:
    sessions_dir = CLAUDE_DIR / "sessions"
    if not sessions_dir.is_dir(): return set()
    ids = set()
    for lock in sessions_dir.glob("*.json"):
        try:    ids.add(json.loads(lock.read_text())["sessionId"])
        except (json.JSONDecodeError, KeyError): continue
    return ids


@dataclass
class Session:
    path        : Path
    first_prompt: str | None = None

    @property
    def uuid(self) -> str: return self.path.stem

    @property
    def mtime(self) -> float: return self.path.stat().st_mtime

    @property
    def date(self) -> str: return datetime.fromtimestamp(self.mtime).strftime("%d %b %Y, %H:%M")

    @property
    def size(self) -> str: return _format_size(self.path.stat().st_size)

    @property
    def name(self) -> str:
        # Display name priority: customTitle (last wins) > aiTitle > firstPrompt > uuid[:8]
        custom = ai = None
        with self.path.open() as f:
            for line in f:
                try:
                    if   '"custom-title"' in line: custom = json.loads(line).get("customTitle", custom)
                    elif '"ai-title"'     in line: ai     = ai or json.loads(line).get("aiTitle")
                except (json.JSONDecodeError, KeyError): continue
        return custom or ai or self.first_prompt or self.uuid[:8]


# ---------------------------------------------------------------------------
#  Operations
# ---------------------------------------------------------------------------

def _remove(path: Path) -> None:
    """Trash where available, rm as fallback. Refuses paths outside ~/.claude/"""
    if not str(path.resolve()).startswith(str(CLAUDE_DIR.resolve())): return

    trash_cmd = {
        "Darwin": ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{path}"'],
        "Linux":  ["gio", "trash", str(path)],
    }.get(platform.system())

    if trash_cmd and subprocess.run(trash_cmd, capture_output=True).returncode == 0: return
    shutil.rmtree(path) if path.is_dir() else path.unlink()


def discover(project: str) -> list[Session]:
    root = project_dir(project)
    if not root: return []
    prompts  = _index_first_prompts(project)
    sessions = [Session(p, prompts.get(p.stem)) for p in root.glob("*.jsonl")]
    return sorted(sessions, key=lambda s: s.mtime, reverse=True)


def delete(uuid: str, project: str) -> None:
    if uuid in _active_session_ids():
        print(f"ERROR: Session {uuid[:8]} is currently active")
        return

    root    = project_dir(project)
    targets = [p for p in [
        root / f"{uuid}.jsonl" if root else None,
        root / uuid if root else None,
        CLAUDE_DIR / "file-history" / uuid,
        CLAUDE_DIR / "session-env"  / uuid,
    ] if p and p.exists()]

    if not targets:
        print(f"No session found: {uuid}")
        return

    for path in targets: _remove(path)

    history = CLAUDE_DIR / "history.jsonl"
    if history.exists():
        lines = history.read_text().splitlines()
        keep  = [line for line in lines if line.strip() and json.loads(line).get("sessionId") != uuid]
        history.write_text("\n".join(keep) + "\n")

    print(f"Deleted: {uuid[:8]} ({len(targets)} items)")


def prune(project: str, max_age: str, confirm: bool = False) -> None:
    multipliers = {"d": 86400, "w": 604800, "m": 2592000}
    cutoff      = time.time() - int(max_age[:-1]) * multipliers[max_age[-1].lower()]
    active      = _active_session_ids()
    old         = [s for s in discover(project) if s.mtime < cutoff and s.uuid not in active]

    if not old:
        print(f"No deletable sessions older than {max_age}.")
        return

    print(f"Sessions older than {max_age}:\n")
    print("| # | Name | UUID | Date | Size |")
    print("|---|------|------|------|------|")
    for i, s in enumerate(old, 1):
        print(f"| {i} | {s.name} | `{s.uuid[:8]}` | {s.date} | {s.size} |")

    if not confirm:
        print(f"\n**{len(old)} sessions** ready to prune.")
        return

    for s in old: delete(s.uuid, project)
    print(f"\nPruned {len(old)} sessions.")


# ---------------------------------------------------------------------------
#  Output
# ---------------------------------------------------------------------------

def print_table(project: str) -> None:
    sessions = discover(project)
    if not sessions:
        print("No sessions found for this project.")
        return

    active = _active_session_ids()
    print(f"**Project directory:** `{project_dir(project)}`\n")
    print("| # | Name | UUID | Date | Size |")
    print("|---|------|------|------|------|")
    for i, s in enumerate(sessions, 1):
        marker = "\u25cf " if s.uuid in active else ""
        print(f"| {i} | {marker}{s.name} | `{s.uuid[:8]}` | {s.date} | {s.size} |")
    print(f"\n**Total sessions:** {len(sessions)}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: list_sessions.py <project> [--delete <uuid>] [--prune <duration> [--confirm]]")
        sys.exit(1)

    project = sys.argv[1]

    if "--delete" in sys.argv:
        delete(sys.argv[sys.argv.index("--delete") + 1], project)
    elif "--prune" in sys.argv:
        prune(project, sys.argv[sys.argv.index("--prune") + 1], "--confirm" in sys.argv)
    else:
        print_table(project)
