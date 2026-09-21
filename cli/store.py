#!/usr/bin/env python3
"""The store Claude Code keeps under ~/.claude — projects, sessions, and their safe removal.

Engine behind the /sessions and /projects skills. It never prints; callers own all
I/O. Every deletion routes through `_remove` (Trash-first, refuses anything outside
~/.claude) and `rewrite_history` (atomic); `nuke` then hands the config entry to
`claude project purge`. Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import json
import os
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

UUID       = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
OFF_LIMITS = {"projects", "sessions", "telemetry"}  # swept per project · live locks · not ours to touch
DISPOSABLE = {"file-history", "session-env", "debug", "tasks", "image-cache", "uploads"}  # per-session folders Claude Code's own age sweep deletes


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


def _owner(name: str) -> str | None:
    """The session a file name belongs to: `<uuid>` or `<uuid>.<suffix>`, and no second uuid anywhere in it."""
    hit = UUID.match(name)
    if not hit: return None
    rest = name[hit.end():]
    return hit[0] if (not rest or rest[0] == ".") and not UUID.search(rest) else None


def strays(uuids: set) -> dict:
    """uuid -> every path outside projects/ named after that session, found in one walk.

    Finding by name keeps pace with Claude Code: a per-session folder it adds tomorrow
    shows up here unasked. Finding is not deleting — see `disposable`.
    """
    found: dict = {u: [] for u in uuids}
    if not CLAUDE_DIR.is_dir(): return found
    for top in CLAUDE_DIR.iterdir():
        if not top.is_dir() or top.is_symlink() or top.name in OFF_LIMITS: continue
        for here, dirs, files in os.walk(top):
            for name in dirs + files:
                if _owner(name) in found: found[_owner(name)].append(Path(here, name))
            deep    = len(Path(here).relative_to(top).parts) >= 2
            dirs[:] = [] if deep else [d for d in dirs if not UUID.search(d)]  # a session's dir is wholly its own
    return found


def shape(path: Path) -> str:
    """A path with everything personal taken out — `daemon/attach-journal/<uuid>.json` — safe to paste in public."""
    return UUID.sub("<uuid>", path.relative_to(CLAUDE_DIR).as_posix())


def disposable(path: Path) -> bool:
    """Only strays in folders Claude Code itself sweeps by age are deleted; the rest are reported, never touched."""
    return path.relative_to(CLAUDE_DIR).parts[0] in DISPOSABLE


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
    shutil.copymode(HISTORY, tmp)  # every prompt you've typed lives here; keep it as private as it was
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
    def local(self) -> list[Path]:
        # transcript, its data dir, and any copy Claude Code set aside — all share the uuid as a name prefix
        return sorted(p for p in self.path.parent.glob(f"{self.uuid}*") if _owner(p.name) == self.uuid)

    @property
    def artifacts(self) -> list[Path]:
        return self.local + [p for p in strays({self.uuid})[self.uuid] if disposable(p)]

    @property
    def unclaimed(self) -> list[Path]:
        return [p for p in strays({self.uuid})[self.uuid] if not disposable(p)]

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
    live = (Session(p) for p in root.glob("*.jsonl") if UUID.fullmatch(p.stem))  # skips set-aside copies
    return sorted(live, key=lambda s: s.mtime, reverse=True)


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

    Returns (purged, bytes_freed), counting only what is verifiably gone. Active
    sessions are skipped — this is the one place that invariant is enforced. Never
    touches a project's `memory/`.
    """
    doomed = [s for s in sessions if s.uuid not in active_ids()]
    extra  = strays({s.uuid for s in doomed})
    freed  = 0
    for s in doomed:
        for path in s.local + [p for p in extra[s.uuid] if disposable(p)]:
            size = _du(path)
            _remove(path)
            if not path.exists(): freed += size
    purged = [s for s in doomed if not s.path.exists()]
    rewrite_history(uuids={s.uuid for s in purged})
    return purged, freed


def claude_version() -> tuple | None:
    exe = shutil.which("claude")
    if not exe: return None
    try:    out = subprocess.run([exe, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired): return None
    version = re.match(r"(\d+)\.(\d+)\.(\d+)", out.strip())
    return tuple(map(int, version.groups())) if version else None


def native_purge() -> list | None:
    """The `claude project purge` command line, if this Claude Code has it (2.1.126+)."""
    return [shutil.which("claude"), "project", "purge", "--yes"] if (claude_version() or ()) >= (2, 1, 126) else None


def nuke(project: Project) -> tuple[int, bool]:
    """Total removal of a project's entire footprint. Returns (bytes_freed, native_ran).

    Everything on disk goes to Trash first: sessions, memory, subagent data, strays,
    the directory, plus the history rows. Then `claude project purge` clears what only
    Claude Code can reach — the project's entry in ~/.claude.json — so nuke stays a
    superset of it. Precondition (caller-enforced): not the current project, no
    active sessions.
    """
    extra = [p for paths in strays({s.uuid for s in project.sessions}).values() for p in paths if disposable(p)]
    freed = _du(project.dir) + sum(_du(p) for p in extra)
    for path in extra: _remove(path)
    _remove(project.dir)
    rewrite_history(uuids={s.uuid for s in project.sessions}, cwds={project.cwd} if project.cwd else frozenset())

    purge_cmd = native_purge() if project.cwd else None
    if not purge_cmd: return freed, False
    try:    done = subprocess.run(purge_cmd + [project.cwd], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired): return freed, False
    # purge exits 1 when the Trash pass above left it nothing to clear; that is a clean finish, not a failure
    return freed, done.returncode == 0 or "No Claude Code project state" in done.stderr


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
