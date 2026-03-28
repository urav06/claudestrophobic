---
name: sessions
description: List, identify, and delete Claude Code conversations for the current project
argument-hint: "[list | delete <name-or-uuid> | browse | prune --older <duration>]"
allowed-tools: [Bash, Read, Glob]
disable-model-invocation: true
---

# Session Manager

You help users manage their Claude Code conversations. Keep responses concise — this is a utility.

## Context

**Sessions** (authoritative — from preprocessor):

```
!`python3 ${CLAUDE_SKILL_DIR}/scripts/list_sessions.py "$PWD"`
```

- **Current session:** `${CLAUDE_SESSION_ID}`
- **Project dir:** `$HOME/.claude/projects/$(echo "$PWD" | tr '/' '-')`

## Commands

Interpret `$ARGUMENTS` and execute the matching command. Default: **list**.

### list

Render the session table as markdown: **Name** (≤60 chars), **UUID** (first 8 chars), **Date**, **Size**.
If `NO_SESSIONS`, say so.

### delete <name-or-uuid>

Match by UUID prefix or fuzzy name (case-insensitive substring). Ambiguous → ask. No match → show full list.

**NEVER delete `${CLAUDE_SESSION_ID}`** — that is THIS conversation.

Procedure:
1. Trash both `<uuid>.jsonl` and `<uuid>` under the project dir:
   - macOS: `osascript -e "tell application \"Finder\" to delete POSIX file \"$PROJECT_DIR/<file>\"" 2>/dev/null`
   - Linux: `gio trash "$PROJECT_DIR/<file>" 2>/dev/null`
2. Purge history: `python3 ${CLAUDE_SKILL_DIR}/scripts/list_sessions.py --purge <uuid>`
3. Confirm what was deleted

### browse

Open the project dir in the system file browser (`open` on macOS, `xdg-open` on Linux).

### prune --older <duration>

Delete sessions older than `<duration>` (`30d` / `2w` / `3m`). Excludes current session.
Show candidates → **confirm** → delete each per the delete procedure above.

## Defaults

- Empty or whitespace → **list**
- Unrecognized argument → treat as session name for **delete**
