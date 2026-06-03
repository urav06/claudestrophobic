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

Claude Code has no built-in way to see, name, or delete your past sessions. They accumulate forever. **claudestrophobic** gives you the controls: list and delete sessions, prune the old ones, and clear out whole projects you've finished, all from the terminal. It ships as skills instead of MCP tools, so it costs **zero tokens** of context until you call it.

## Why

On claude.ai, every conversation sits in a sidebar. Named. Browsable. Deletable. Claude Code keeps the very same conversations as opaque UUID files under `~/.claude/projects/`, with nothing built in to manage them. The [request to fix that](https://github.com/anthropics/claude-code/issues/13514) has been open for over ten months, unanswered.

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
- **Deletion** clears a session's whole footprint: transcript, subagent data, file history, session environment, and its rows in `history.jsonl`.
- **Projects** are keyed by their real working directory, read from the transcript rather than the lossy encoded folder name. That is how it finds sessions stranded when you delete a project folder, which Claude Code never cleans up on its own.
- **`nuke`** retires a finished project in one move: every session, its memory, its history, the directory. It refuses the project you are in and any with a live session.
- **Safety** is the default. Active sessions are read from lock files and left untouched. History rewrites are atomic, so a session running alongside never sees a half-written file. Everything removed goes to the system Trash where one exists, with `rm` as the fallback. macOS and Linux.
- **Zero tokens.** Skills load only when you call them. An MCP server with these features would crowd every prompt you send; this stays out of your context until you ask. The whole thing is a few hundred lines of dependency-free Python.
