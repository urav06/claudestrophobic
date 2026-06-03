---
name: projects
description: List all Claude Code projects and nuke ones you're finished with
argument-hint: "[list | nuke <name> [--confirm] | browse <name>]"
disable-model-invocation: true
allowed-tools: Bash
---

# All Claude Code projects

Run: `python3 "${CLAUDE_PLUGIN_ROOT}/cli/cc.py" projects "${CLAUDE_PROJECT_DIR}" <command>`

| Intent | `<command>` |
|--------|-------------|
| List every project | *(omit)* |
| Preview a nuke | `nuke <name>` |
| Confirm a nuke | `nuke <name> --confirm` |
| Open a project's folder | `browse <name>` |

`nuke` TOTALLY removes a project's Claude Code footprint — every session, its
memory, history entries, and the directory — to the system Trash. It refuses
the project you're currently in and any project with an active session.

Resolve the user's phrase to one project from the list, then pass a
distinguishing substring (usually the folder name) as `<name>`. Projects shown
as **orphaned** (the folder is gone) or **empty** are the usual nuke targets.
