---
name: sessions
description: List and manage Claude Code sessions for this project
argument-hint: "[list | delete <name> | browse | prune --older <duration>]"
disable-model-invocation: true
allowed-tools: Bash
---

# Session management

Script: `python3 ${CLAUDE_SKILL_DIR}/scripts/list_sessions.py "$PWD"`

| Command | Flags |
|---------|-------|
| List sessions | *(none)* |
| Delete session | `--delete <full-uuid>` |
| Preview old sessions | `--prune <duration>` |
| Delete old sessions | `--prune <duration> --confirm` |
| Browse | open the **Project directory** path from list output |

For `delete`, list first to identify the target UUID by fuzzy name or prefix match.
Sessions marked ● are active and protected from deletion.
