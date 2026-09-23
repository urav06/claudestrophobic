#!/usr/bin/env python3
"""claudestrophobic: manage Claude Code sessions and projects from the terminal.

  cc.py sessions <cwd> [delete <uuid-prefix> [--preview] | browse]
  cc.py projects <cwd> [delete <name|orphaned|dormant> [--confirm] | browse <name>]

`store` sits beside this file, so a bare import resolves with no path setup.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from urllib.parse import urlencode

import store


ISSUES  = "https://github.com/urav06/claudestrophobic/issues"
OPTIONS = {"--confirm", "--preview", "--dry-run"}


# ---------------------------------------------------------------------------
#  sessions — the current project's own sessions
# ---------------------------------------------------------------------------

def sessions_list(cwd: str) -> None:
    sessions = store.discover(cwd)
    if not sessions:
        print("No sessions in this project yet. Roomy in here."); return
    active = store.active_ids()
    print(f"**Project:** `{store.project_dir(cwd)}`\n")
    print("| # | Session | UUID | Last active | Size |")
    print("|---|------|------|-------------|------|")
    for i, s in enumerate(sessions, 1):
        dot = "● " if s.uuid in active else ""
        print(f"| {i} | {dot}{s.name} | `{s.uuid[:8]}` | {store.fmt_age(s.mtime)} | {store.fmt_size(s.size)} |")
    print(f"\n**{len(sessions)} sessions** · {store.fmt_size(sum(s.size for s in sessions))} total")


def sessions_delete(cwd: str, selector: str, dry_run: bool) -> None:
    hits = [s for s in store.discover(cwd) if selector and s.uuid.startswith(selector)]
    if not hits:
        print(f"No session matches `{selector}`. Run `/sessions` to see UUIDs."); return
    if len(hits) > 1:
        print(f"`{selector}` matches {len(hits)} sessions. Narrow it down:\n")
        for s in hits: print(f"- `{s.uuid[:8]}` {s.name}")
        return

    s = hits[0]
    if s.uuid in store.active_ids():
        print(f"● `{s.uuid[:8]}` is the session you're in, so it can't be deleted from here."); return
    name = s.name
    if dry_run:
        print(f"Deleting **{name}** would remove:\n")
        for path in s.artifacts: print(f"- `~/.claude/{path.relative_to(store.CLAUDE_DIR)}` ({store.fmt_size(store._du(path))})")
        print("- its rows in `history.jsonl`")
        _report_unclaimed(s.unclaimed)
        print("\nThis was a preview. Nothing was deleted."); return
    unclaimed = s.unclaimed
    purged, freed = store.purge([s])
    if not purged:
        print(f"Couldn't delete **{name}**. Its transcript is still on disk."); return
    print(f"Deleted **{name}**. Freed {store.fmt_size(freed)}.")
    _report_unclaimed(unclaimed)


def _report_unclaimed(paths: list) -> None:
    """Files named after the session in folders this tool doesn't know. Left alone, and worth a bug report.

    The link's query keys are the field ids in .github/ISSUE_TEMPLATE/unclaimed-path.yml; rename them together.
    """
    if not paths: return
    found   = sorted({f"{store.shape(p)}  ({'folder' if p.is_dir() else 'file'}, {store.fmt_size(store._du(p))})" for p in paths})
    folders = sorted({str(Path(store.shape(p)).parent) for p in paths})
    version = ".".join(map(str, store.claude_version() or ())) or "unknown"
    report  = ISSUES + "/new?" + urlencode({
        "template": "unclaimed-path.yml",
        "title":    "Unclaimed path: " + ", ".join(folders),
        "paths":    "\n".join(found),
        "plugin":   _plugin_version(),
        "claude":   version,
        "os":       f"{platform.system()} {platform.release()}",
    })
    print("\nNot deleted. These are named after this session, but claudestrophobic doesn't know the folder:\n")
    for line in found: print(f"- `~/.claude/{line.split('  (')[0]}`")
    print(f"\n[Report this folder]({report}) so a later version can handle it.")


def _plugin_version() -> str:
    try:    return json.loads((Path(__file__).parent.parent / ".claude-plugin" / "plugin.json").read_text())["version"]
    except (OSError, KeyError, json.JSONDecodeError): return "unknown"


def sessions_browse(cwd: str) -> None:
    root = store.project_dir(cwd)
    if not root: print("No project directory yet."); return
    store.reveal(root)
    print(f"Opened `{root}`")


# ---------------------------------------------------------------------------
#  projects: the whole map; delete the ones you are finished with
# ---------------------------------------------------------------------------

def _one_project(selector: str) -> store.Project | None:
    """Resolve a name to exactly one project, or print why it couldn't and return None.

    A project is named by its full path, its folder name, or its trailing path
    components: `kit-ctf` and `code/kit-ctf` both mean `/Users/urav/code/kit-ctf`.
    Never a substring, since `/Users/urav` is inside every path beneath it.
    """
    sel  = selector.strip().rstrip("/")
    hits = [p for p in store.all_projects() if sel and (sel in (p.name, p.dir.name) or p.name.endswith("/" + sel))]
    if len(hits) == 1: return hits[0]
    if not hits:
        print(f"No project matches `{selector}`.")
    else:
        print(f"`{selector}` matches {len(hits)} projects. Narrow it down:\n")
        for p in hits: print(f"- {p.name}")
    return None


def projects_list(cwd: str) -> None:
    projects = store.all_projects()
    if not projects:
        print("No projects found."); return
    current = store.project_dir(cwd)
    print("| # | Project | Sessions | Memory | Last active | Size | State |")
    print("|---|---------|----------|--------|-------------|------|-------|")
    for i, p in enumerate(projects, 1):
        here = " (you're here)" if p.dir == current else ""
        print(f"| {i} | {p.name}{here} | {len(p.sessions)} | {store.fmt_size(p.memory) if p.memory else ''} | "
              f"{store.fmt_age(p.last_active)} | {store.fmt_size(p.size)} | {p.state} |")
    orphaned = [p for p in projects if p.state == "orphaned"]
    dormant  = [p for p in projects if p.state == "dormant"]
    if orphaned:
        print(f"\n**{len(orphaned)} orphaned**: their folders are gone, so Claude Code will never read what it kept for them. "
              f"{store.fmt_size(sum(p.size for p in orphaned))}. `/projects delete orphaned` removes them all.")
    if dormant:
        print(f"\n**{len(dormant)} dormant**: no sessions left, but their memory loads the next time Claude runs there.")


def _targets(cwd: str, selector: str) -> list:
    """The projects a selector names: `orphaned` or `dormant` for every project in that state, else one by name."""
    if selector in ("orphaned", "dormant"):
        found = [p for p in store.all_projects() if p.state == selector]
        if not found: print(f"No {selector} projects.")
        return found
    p = _one_project(selector)
    return [p] if p else []


def projects_delete(cwd: str, selector: str, confirm: bool) -> None:
    targets = _targets(cwd, selector)
    if not targets: return
    here, active = store.project_dir(cwd), store.active_ids()
    for p in targets:
        if p.dir == here:
            print("Can't delete the project you're standing in. Run this from another folder."); return
        if {s.uuid for s in p.sessions} & active:
            print(f"**{p.name}** has an active session. Close it first."); return

    if not confirm:
        print(f"**Delete {len(targets)} projects?**" if len(targets) > 1 else f"**Delete {targets[0].name}?**")
        print("This removes everything Claude Code keeps for each one: sessions, memory, history rows, and its folder.\n")
        for p in targets:
            parts = [f"{len(p.sessions)} sessions"] + ([f"memory {store.fmt_size(p.memory)}"] if p.memory else [])
            print(f"- **{p.name}** ({', '.join(parts)}, {store.fmt_size(p.size)})")
        if store.native_purge() and any(p.cwd for p in targets):
            print("\n`claude project purge` then removes the entry in `~/.claude.json` (trust, MCP servers), permanently.")
        print(f"\nFiles go to the Trash. {store.fmt_size(sum(p.size for p in targets))} reclaimable. Re-run with `--confirm`.")
        return

    freed, unpurged = 0, []
    for p in targets:
        got, native = store.delete_project(p)
        freed += got
        if p.cwd and not native: unpurged.append(p.cwd)
    what = targets[0].name if len(targets) == 1 else f"{len(targets)} projects"
    print(f"Deleted **{what}**. Freed {store.fmt_size(freed)}. Breathe easier.")
    for cwd_ in unpurged:
        print(f"\nCouldn't run `claude project purge`, so the entry for `{cwd_}` in `~/.claude.json` may still be there. "
              f"To check: `claude project purge --dry-run {cwd_}`")


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
    dry_run = "--preview" in rest or "--dry-run" in rest
    # the selector is the first token that isn't an option; it may start with one dash, since
    # every project folder name does (`-Users-urav`). Anything else dash-led must be a known option.
    arg     = next((a for a in rest[1:] if a not in OPTIONS and not a.startswith("--")), "")
    unknown = [a for a in rest if a.startswith("-") and a not in OPTIONS and a != arg]
    if unknown:  # a misspelt --preview must never fall through to a real delete
        print(f"Unknown option `{unknown[0]}`. Nothing was done.\n{__doc__}"); return

    if noun == "sessions":
        if   verb == "delete": sessions_delete(cwd, arg, dry_run)
        elif verb == "browse": sessions_browse(cwd)
        else:                  sessions_list(cwd)
    elif noun == "projects":
        if   verb == "delete": projects_delete(cwd, arg, confirm)
        elif verb == "browse": projects_browse(cwd, arg)
        else:                  projects_list(cwd)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
