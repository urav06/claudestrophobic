#!/usr/bin/env python3
"""claudestrophobic — manage Claude Code sessions and projects from the terminal.

  cc.py sessions <cwd> [delete <uuid-prefix> | prune <duration> [--confirm] | browse]
  cc.py projects <cwd> [nuke <name> [--confirm] | browse <name>]

`store` sits beside this file, so a bare import resolves with no path setup.
"""

from __future__ import annotations

import sys
import time

import store


# ---------------------------------------------------------------------------
#  sessions — the current project's own sessions
# ---------------------------------------------------------------------------

def sessions_list(cwd: str) -> None:
    sessions = store.discover(cwd)
    if not sessions:
        print("No sessions in this project yet — roomy in here."); return
    active = store.active_ids()
    print(f"**Project:** `{store.project_dir(cwd)}`\n")
    print("| # | Session | UUID | Last active | Size |")
    print("|---|------|------|-------------|------|")
    for i, s in enumerate(sessions, 1):
        dot = "● " if s.uuid in active else ""
        print(f"| {i} | {dot}{s.name} | `{s.uuid[:8]}` | {store.fmt_age(s.mtime)} | {store.fmt_size(s.size)} |")
    print(f"\n**{len(sessions)} sessions** · {store.fmt_size(sum(s.size for s in sessions))} total")


def sessions_delete(cwd: str, selector: str) -> None:
    root = store.project_dir(cwd)
    hits = sorted(root.glob(f"{selector}*.jsonl")) if (root and selector) else []
    if not hits:
        print(f"No session matches `{selector}`. Run `/sessions` to see UUIDs."); return
    if len(hits) > 1:
        print(f"`{selector}` matches {len(hits)} sessions — narrow it down:")
        for p in hits: print(f"  · `{p.stem[:8]}`")
        return

    s = store.Session(hits[0])
    if s.uuid in store.active_ids():
        print(f"● `{s.uuid[:8]}` is the session you're in — can't delete it from inside."); return
    name = s.name
    _, freed = store.purge([s])
    print(f"Deleted **{name}** — freed {store.fmt_size(freed)}.")


def sessions_prune(cwd: str, duration: str, confirm: bool) -> None:
    secs = store.parse_age(duration)
    if secs is None:
        print(f"Unrecognised duration `{duration}`. Try `3d`, `2w`, `6m`, `12h`."); return
    cutoff = time.time() - secs
    active = store.active_ids()
    old    = [s for s in store.discover(cwd) if s.mtime < cutoff and s.uuid not in active]
    if not old:
        print(f"No sessions older than {duration}."); return

    print(f"Sessions older than {duration}:\n")
    print("| # | Session | UUID | Last active | Size |")
    print("|---|------|------|-------------|------|")
    for i, s in enumerate(old, 1):
        print(f"| {i} | {s.name} | `{s.uuid[:8]}` | {store.fmt_age(s.mtime)} | {store.fmt_size(s.size)} |")

    if not confirm:
        print(f"\n**{len(old)} sessions** · {store.fmt_size(sum(s.size for s in old))} reclaimable. "
              f"Re-run with `--confirm` to prune."); return
    _, freed = store.purge(old)
    print(f"\nPruned {len(old)} sessions — freed {store.fmt_size(freed)}.")


def sessions_browse(cwd: str) -> None:
    root = store.project_dir(cwd)
    if not root: print("No project directory yet."); return
    store.reveal(root)
    print(f"Opened `{root}`")


# ---------------------------------------------------------------------------
#  projects — the whole map; nuke ones you're finished with
# ---------------------------------------------------------------------------

def _one_project(selector: str) -> store.Project | None:
    """Resolve a substring to exactly one project, or print why it couldn't and return None."""
    hits = [p for p in store.all_projects() if selector and selector.lower() in p.name.lower()]
    if len(hits) == 1: return hits[0]
    if not hits:
        print(f"No project matches `{selector}`.")
    else:
        print(f"`{selector}` matches {len(hits)} projects — narrow it down:")
        for p in hits: print(f"  · {p.name}")
    return None


def projects_list(cwd: str) -> None:
    projects = store.all_projects()
    if not projects:
        print("No projects found."); return
    current = store.project_dir(cwd)
    print("| # | Project | Sessions | Last active | Size | State |")
    print("|---|---------|-------|-------------|------|-------|")
    for i, p in enumerate(projects, 1):
        here = "  ← you're here" if p.dir == current else ""
        print(f"| {i} | {p.name}{here} | {len(p.sessions)} | {store.fmt_age(p.last_active)} | "
              f"{store.fmt_size(p.size)} | {p.state} |")
    stale = [p for p in projects if not p.live]
    if stale:
        print(f"\n**{len(stale)} projects** orphaned or empty · {store.fmt_size(sum(p.size for p in stale))} "
              f"reclaimable · nuke one with `/projects nuke <name>`")


def projects_nuke(cwd: str, selector: str, confirm: bool) -> None:
    p = _one_project(selector)
    if p is None: return
    if p.dir == store.project_dir(cwd):
        print("Can't nuke the project you're standing in — run this from another folder."); return
    if {s.uuid for s in p.sessions} & store.active_ids():
        print(f"**{p.name}** has an active session — close it first."); return

    if not confirm:
        print(f"**Nuke {p.name}?** This removes its entire Claude Code footprint:\n")
        print(f"- {len(p.sessions)} sessions")
        if p.memory: print(f"- memory ({store.fmt_size(p.memory)})")
        print("- history entries + the project directory\n")
        print(f"Everything goes to Trash · {store.fmt_size(p.size)} reclaimable. Re-run with `--confirm`.")
        return
    freed = store.nuke(p)
    print(f"Nuked **{p.name}** → Trash. Freed {store.fmt_size(freed)}. Breathe easier.")


def projects_browse(cwd: str, selector: str) -> None:
    p = _one_project(selector)
    if p is None: return
    store.reveal(p.dir)
    print(f"Opened `{p.dir}`")


# ---------------------------------------------------------------------------

def main(argv: list) -> None:
    if len(argv) < 2:
        print(__doc__); return
    noun, cwd, rest = argv[0], argv[1], argv[2:]
    verb    = rest[0] if rest else ""
    confirm = "--confirm" in rest
    arg     = next((a for a in rest[1:] if not a.startswith("-")), "")

    if noun == "sessions":
        if   verb == "delete": sessions_delete(cwd, arg)
        elif verb == "prune":  sessions_prune(cwd, arg, confirm)
        elif verb == "browse": sessions_browse(cwd)
        else:                  sessions_list(cwd)
    elif noun == "projects":
        if   verb == "nuke":   projects_nuke(cwd, arg, confirm)
        elif verb == "browse": projects_browse(cwd, arg)
        else:                  projects_list(cwd)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
