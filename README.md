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

Claude Code lets you resume and rename past sessions, but not delete one. **claudestrophobic** adds that: delete a session, prune old ones, and find and remove the projects you have finished, all from the terminal. It ships as skills instead of MCP tools, so it costs **zero tokens** of context until you call it.

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
/sessions prune --older 2w            # drop everything older than two weeks
/sessions browse                      # open the project's folder
```

**`/projects`** works across all of them, from the outside:

```
/projects                             # every project: session count, size, live or orphaned
/projects nuke old-project            # preview what nuke would remove
/projects nuke old-project --confirm  # remove it: sessions, memory, history, folder, to Trash
```

## How it works

- **Names** come from each session's own transcript, the same chain Claude Code's resume picker uses: your `/rename` title, then the auto-generated one, then the first prompt.
- **Deletion** finds a session's files by name, anywhere under `~/.claude`, then removes only the ones in folders Claude Code itself treats as disposable: the transcript, subagent data, file history, session environment, debug log, and its rows in `history.jsonl`. Anything it finds elsewhere is left alone and printed with a pre-filled link to report it.
- **Projects** are keyed by their real working directory, read from the transcript rather than the lossy encoded folder name. That is how it finds sessions stranded when you delete a project folder, which Claude Code never cleans up on its own.
- **`nuke`** removes a finished project: every session, its memory, its history, the directory, all to the Trash. It then runs Claude Code's own `claude project purge` to clear the project's entry in `~/.claude.json`, so it covers everything purge does and keeps the files recoverable. It refuses the project you are in and any with a live session.
- **Safety** is the default. Active sessions are read from lock files and left untouched. History rewrites are atomic, so a session running alongside never sees a half-written file. Everything removed goes to the system Trash where one exists, with `rm` as the fallback. macOS and Linux.
- **Zero tokens.** Skills load only when you call them. An MCP server with these features would crowd every prompt you send; this stays out of your context until you ask. The whole thing is a few hundred lines of dependency-free Python.
