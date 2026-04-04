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

A [Claude Code](https://claude.ai/code) plugin that brings conversation management back — list, delete, and prune sessions without leaving the terminal. Built as a skill, not an MCP tool, so it occupies **zero tokens** in your context window until you invoke it.

## Install

```
/plugin marketplace add urav/claudestrophobic
/plugin install claudestrophobic
```

## Usage

```
/sessions                              # list all sessions
/sessions delete fix auth middleware   # delete by name (fuzzy match)
/sessions delete 064ddd26             # delete by partial UUID
/sessions prune --older 2w            # delete sessions older than 2 weeks
/sessions browse                      # open project's .claude directory
```

## Why

On claude.ai, your conversations live in a sidebar. Named, browsable, deletable. In Claude Code, they become invisible UUID files under `~/.claude/projects/`. There is no built-in way to delete them. This has been [one of the most requested features](https://github.com/anthropics/claude-code/issues/13514) for over 10 months — with no response from Anthropic.

This brings that visibility back.

## How it works

- **Names** resolved from session transcript metadata — `/rename` titles, auto-generated titles, or first message. Same priority chain Claude Code uses internally.
- **Deletion** informed by Claude Code's recently surfaced internals — cleans transcripts, subagent data, file history, and session environment. Nothing left dangling.
- **Safety** — active sessions detected from lock files and protected from deletion. System Trash where available, `rm` as fallback. Cross-platform.
- **Overhead** — only loads into context when you type `/sessions`. Zero tokens otherwise.
