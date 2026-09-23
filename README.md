<div align="center">

# claudestrophobic

*Because `064ddd26-9a3f-...` is not a name.*

<a href="https://github.com/urav06/claudestrophobic/stargazers"><img src="https://img.shields.io/github/stars/urav06/claudestrophobic?style=social" alt="Stars"/></a>

<img src="https://img.shields.io/badge/Claude_Code-Plugin-5A67D8" alt="Claude Code Plugin"/>
<img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
<img src="https://img.shields.io/badge/context_overhead-zero-black" alt="Zero context overhead"/>

<br>

<img src="https://github.com/user-attachments/assets/9f6ad16c-1b13-4336-81d5-faea0eb3eedd" alt="demo" width="680"/>

</div>

---

Claude Code lets you resume and rename past sessions, but not delete one. **claudestrophobic** adds that: delete a session, and find and remove the projects you have finished, all from the terminal. It ships as skills instead of MCP tools, so it costs **zero tokens** of context until you call it.

## Why

On claude.ai you can delete a conversation from the sidebar. Claude Code keeps the same conversations as UUID-named files under `~/.claude/projects/`, and the only built-in removal is a sweep that deletes everything older than 30 days.

This is that sidebar, brought to your terminal.

## Install

```
/plugin marketplace add urav06/claudestrophobic
/plugin install claudestrophobic@claudestrophobic-marketplace
```

## Usage

**`/sessions`** works inside the project you're in:

```
/sessions                             # list this project's sessions
/sessions delete the one about auth   # delete by description; the model finds the match
/sessions delete 064ddd26             # or by UUID prefix
/sessions delete 064ddd26 --preview   # show what a delete would remove
/sessions browse                      # open the project's folder
```

**`/projects`** works across all of them, from the outside:

```
/projects                             # every project, with its state: orphaned, dormant, or in use
/projects delete old-project          # preview what a delete would remove
/projects delete orphaned --confirm   # remove every orphaned project: sessions, memory, history, folder
```

## How it works

- **Names** come from each session's own transcript, the same chain Claude Code's resume picker uses: your `/rename` title, then the auto-generated one, then the first prompt.
- **Deletion** finds a session's files by name, anywhere under `~/.claude`, then removes only the ones in folders Claude Code itself treats as disposable: the transcript, subagent data, file history, session environment, debug log, and its rows in `history.jsonl`. It leaves anything found elsewhere alone and prints a pre-filled link to report it.
- **Projects** are keyed by their real working directory, read from a transcript, or from `history.jsonl` and `~/.claude.json` once the transcripts are gone.
- **Orphaned** means the project's directory no longer exists. Claude Code keeps its memory, history rows, and config entry forever, and nothing native notices. **Dormant** means the directory exists but no sessions do: the 30-day sweep took the conversations and kept the memory on purpose, and that memory loads the next time you run Claude there.
- **Deleting a project** removes every session, its memory, its history rows, and the directory, all to the Trash. It then runs Claude Code's own `claude project purge` to clear the project's entry in `~/.claude.json`, so it covers everything purge does and keeps the files recoverable. It refuses the project you are in and any with a live session.
- **Sandboxed sessions are told, not failed.** Claude Code's sandbox blocks reads of `history.jsonl` and `~/.claude.json` and writes under `~/.claude`. When that happens the list says which paths and states it couldn't verify, and a delete reports what the OS refused instead of stopping halfway. A `--confirm` only ever removes the set its preview showed; if that set changed in between, it refuses and previews again.
- **Active sessions are never touched.** They are read from Claude Code's lock files and refused. History rewrites are atomic, so a session running alongside never sees a half-written file. Everything removed goes to the system Trash where one exists, with `rm` as the fallback. macOS and Linux.
- **Zero tokens.** Skills load only when you call them. An MCP server with these features would add its tool definitions to every prompt you send; this stays out of your context until you ask. The whole thing is a few hundred lines of dependency-free Python.
