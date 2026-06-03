#!/usr/bin/env python3
"""The store Claude Code keeps under ~/.claude — projects, sessions, and their safe removal.

Engine behind the /sessions and /projects skills. It never prints; callers own all
I/O. Every deletion routes through `_remove` (Trash-first, refuses anything outside
~/.claude) and `rewrite_history` (atomic). Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude"
PROJECTS   = CLAUDE_DIR / "projects"
HISTORY    = CLAUDE_DIR / "history.jsonl"


# ---------------------------------------------------------------------------
#  Path encoding & history index — mirrors Claude Code internals
# ---------------------------------------------------------------------------

def encode(cwd: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "-", cwd)


def project_dir(cwd: str) -> Path | None:
    encoded = encode(cwd)
    direct  = PROJECTS / encoded
    if direct.is_dir(): return direct
    if len(encoded) > 200 and PROJECTS.is_dir():
        return next((d for d in PROJECTS.iterdir() if d.is_dir() and d.name.startswith(encoded[:200])), None)
    return None


def history_cwd() -> dict:
    """sessionId -> project cwd, from history.jsonl. A fallback for projects whose transcripts can't be read."""
    out: dict = {}
    if not HISTORY.exists(): return out
    with HISTORY.open() as f:
        for line in f:
            try: entry = json.loads(line)
            except json.JSONDecodeError: continue
            sid, project = entry.get("sessionId"), entry.get("project")
            if sid and project: out.setdefault(sid, project)
    return out


# ---------------------------------------------------------------------------
#  Removal primitives — the only code that deletes anything
# ---------------------------------------------------------------------------

def _du(path: Path) -> int:
    if path.is_dir(): return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    try:    return path.stat().st_size
    except OSError: return 0


def _satellites(uuid: str) -> list[Path]:
    return [CLAUDE_DIR / "file-history" / uuid, CLAUDE_DIR / "session-env" / uuid]


def _remove(path: Path) -> None:
    """Trash where available, rm as fallback. Refuses anything not strictly under ~/.claude/."""
    if not path.exists(): return
    if CLAUDE_DIR.resolve() not in path.resolve().parents: return

    trash = {
        "Darwin": ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{path}"'],
        "Linux":  ["gio", "trash", str(path)],
    }.get(platform.system())

    try:
        if trash and subprocess.run(trash, capture_output=True).returncode == 0: return
    except OSError: pass  # trash tool absent → fall through to rm
    shutil.rmtree(path) if path.is_dir() else path.unlink()


def active_ids() -> set:
    locks = CLAUDE_DIR / "sessions"
    if not locks.is_dir(): return set()
    ids = set()
    for lock in locks.glob("*.json"):
        try:    ids.add(json.loads(lock.read_text())["sessionId"])
        except (json.JSONDecodeError, KeyError, OSError): continue
    return ids


def rewrite_history(uuids: set = frozenset(), cwds: set = frozenset()) -> None:
    """Drop history rows matching `uuids` or `cwds`. Atomic; keeps unparseable lines."""
    if not (uuids or cwds) or not HISTORY.exists(): return

    def keep(line: str) -> bool:
        try:    entry = json.loads(line)
        except json.JSONDecodeError: return True  # never drop what we can't classify
        return entry.get("sessionId") not in uuids and entry.get("project") not in cwds

    kept = [ln for ln in HISTORY.read_text().splitlines() if ln.strip() and keep(ln)]
    tmp  = HISTORY.with_name(HISTORY.name + ".tmp")
    tmp.write_text("\n".join(kept) + "\n")
    tmp.replace(HISTORY)  # atomic: a concurrent writer never sees a half-written file


# ---------------------------------------------------------------------------
#  Entities
# ---------------------------------------------------------------------------

def _prompt_of(entry: dict) -> str | None:
    """First-prompt for a transcript user line — the slash command or the text, skipping caveat/meta turns."""
    message = entry.get("message")
    content = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    if not isinstance(content, str): return None
    command = re.search(r"<command-name>([^<]+)</command-name>", content)
    if command: return command.group(1).strip()
    if "<local-command-caveat>" in content or "<command-message>" in content: return None
    content = content.strip()
    return " ".join(content.split())[:80] if content else None


@dataclass
class Session:
    path: Path

    @property
    def uuid(self) -> str: return self.path.stem

    @property
    def mtime(self) -> float: return self.path.stat().st_mtime

    @property
    def size(self) -> int: return self.path.stat().st_size

    @property
    def artifacts(self) -> list[Path]:
        here = [self.path, self.path.parent / self.uuid]  # transcript + subagent dir
        return [p for p in here + _satellites(self.uuid) if p.exists()]

    @property
    def name(self) -> str:
        # Self-describing from the transcript, mirroring the native resume UI:
        # customTitle (last /rename wins) > aiTitle (first) > first prompt > uuid[:8]
        custom = ai = prompt = None
        with self.path.open() as f:
            for line in f:
                try:
                    if   '"custom-title"' in line:                   custom = json.loads(line).get("customTitle", custom)
                    elif '"ai-title"'     in line:                   ai     = ai or json.loads(line).get("aiTitle")
                    elif prompt is None and '"type":"user"' in line: prompt = _prompt_of(json.loads(line))
                except json.JSONDecodeError: continue
        return custom or ai or prompt or self.uuid[:8]


@dataclass
class Project:
    dir     : Path
    cwd     : str | None       # canonical working dir, read losslessly from a transcript
    sessions: list[Session]

    @property
    def name(self) -> str: return self.cwd or self.dir.name

    @property
    def live(self) -> bool: return self.cwd is not None and Path(self.cwd).is_dir()

    @property
    def size(self) -> int: return _du(self.dir)

    @property
    def memory(self) -> int: return _du(self.dir / "memory")

    @property
    def state(self) -> str: return "live" if self.live else "orphaned" if self.sessions else "empty"

    @property
    def last_active(self) -> float:
        return max((s.mtime for s in self.sessions), default=self.dir.stat().st_mtime)


# ---------------------------------------------------------------------------
#  Discovery
# ---------------------------------------------------------------------------

def _sessions_in(root: Path) -> list[Session]:
    return sorted((Session(p) for p in root.glob("*.jsonl")), key=lambda s: s.mtime, reverse=True)


def _cwd_of(pdir: Path, hist: dict) -> str | None:
    """Canonical working dir for a project — read from a transcript, falling back to history."""
    for jf in pdir.glob("*.jsonl"):
        try:
            with jf.open() as f:
                for _, line in zip(range(40), f):
                    try:    cwd = json.loads(line).get("cwd")
                    except json.JSONDecodeError: continue
                    if cwd: return cwd
        except OSError: pass
        if jf.stem in hist: return hist[jf.stem]
    return None


def discover(cwd: str) -> list[Session]:
    root = project_dir(cwd)
    return _sessions_in(root) if root else []


def all_projects() -> list[Project]:
    if not PROJECTS.is_dir(): return []
    hist  = history_cwd()
    found = [Project(d, _cwd_of(d, hist), _sessions_in(d)) for d in PROJECTS.iterdir() if d.is_dir()]
    return sorted(found, key=lambda p: p.last_active, reverse=True)


# ---------------------------------------------------------------------------
#  Operations — delete a session, prune old sessions, nuke a whole project
# ---------------------------------------------------------------------------

def purge(sessions: list[Session]) -> tuple[list[Session], int]:
    """Remove every artifact of each non-active session, then one atomic history rewrite.

    Returns (purged, bytes_freed). Active sessions are skipped — this is the one
    place that invariant is enforced. Never touches a project's `memory/`.
    """
    doomed = [s for s in sessions if s.uuid not in active_ids()]
    freed  = 0
    for s in doomed:
        for path in s.artifacts:
            freed += _du(path)
            _remove(path)
    rewrite_history(uuids={s.uuid for s in doomed})
    return doomed, freed


def nuke(project: Project) -> int:
    """Total removal of a project's entire footprint → Trash. Returns bytes freed.

    Takes everything: sessions, memory, subagent data, out-of-dir satellites, history
    rows, and the directory. Precondition (caller-enforced): not the current
    project, no active sessions.
    """
    freed = _du(project.dir) + sum(_du(p) for s in project.sessions for p in _satellites(s.uuid))
    for s in project.sessions:
        for path in _satellites(s.uuid): _remove(path)
    _remove(project.dir)
    rewrite_history(uuids={s.uuid for s in project.sessions}, cwds={project.cwd} if project.cwd else frozenset())
    return freed


# ---------------------------------------------------------------------------
#  Formatting & shell
# ---------------------------------------------------------------------------

def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024: return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_age(ts: float) -> str:
    secs = time.time() - ts
    for span, unit in ((31536000, "y"), (2592000, "mo"), (604800, "w"), (86400, "d"), (3600, "h"), (60, "m")):
        if secs >= span: return f"{int(secs // span)}{unit} ago"
    return "just now"


def parse_age(s: str) -> int | None:
    units = {"h": 3600, "d": 86400, "w": 604800, "m": 2592000}
    match = re.fullmatch(r"(\d+)([hdwm])", s.strip().lower())
    return int(match[1]) * units[match[2]] if match else None


def reveal(path: Path) -> None:
    opener = {"Darwin": "open", "Linux": "xdg-open"}.get(platform.system(), "open")
    subprocess.run([opener, str(path)], capture_output=True)
