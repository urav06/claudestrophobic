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

A [Claude Code](https://claude.ai/code) plugin that brings conversation management back — list, delete, and prune chats, and clean up whole projects, without leaving the terminal. Built as skills, not MCP tools, so they occupy **zero tokens** in your context window until you invoke them.

## Install

```
/plugin marketplace add urav06/claudestrophobic
/plugin install claudestrophobic@claudestrophobic-marketplace
```

## Usage

**`/sessions`** — chats in the project you're in:

```
/sessions                              # list this project's chats
/sessions delete the one about auth    # delete by description (resolved to a chat)
/sessions delete 064ddd26              # …or by UUID prefix
/sessions prune --older 2w             # delete chats older than 2 weeks
/sessions browse                       # open this project's folder
```

**`/projects`** — the whole map, managed from outside:

```
/projects                              # list every project: chats, size, live / orphaned
/projects nuke them-ctf                # preview removing a project you're done with
/projects nuke them-ctf --confirm      # …then nuke it: chats, memory, history, dir → Trash
```

## Why

On claude.ai, your conversations live in a sidebar. Named, browsable, deletable. In Claude Code, they become invisible UUID files under `~/.claude/projects/`. There is no built-in way to delete them. This has been [one of the most requested features](https://github.com/anthropics/claude-code/issues/13514) for over 10 months — with no response from Anthropic.

This brings that visibility back.

## How it works

- **Names** resolved from chat transcript metadata — `/rename` titles, auto-generated titles, or first message. Same priority chain Claude Code uses internally.
- **Deletion** informed by Claude Code's surfaced internals — cleans transcripts, subagent data, file history, session environment, and history rows. Nothing left dangling.
- **Projects** discovered by their *real* working directory, read losslessly from the transcript (not the lossy encoded folder name) — so chats orphaned by a deleted folder are detected and reclaimable. Claude Code never cleans these up on its own.
- **`nuke`** is total and deliberate: it takes a finished project's chats, memory, history, and directory in one go. It refuses the project you're currently in and any project with an active chat.
- **Safety** — active chats detected from lock files and protected. History rewrites are atomic (a concurrent session never sees a half-written file). Everything goes to the system Trash where available, `rm` as fallback. Cross-platform.
- **Overhead** — only loads into context when you invoke a skill. Zero tokens otherwise.
