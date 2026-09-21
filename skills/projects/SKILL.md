---
name: projects
description: List all Claude Code projects and nuke ones you're finished with
argument-hint: "[list | nuke <name> [--confirm] | browse <name>]"
disable-model-invocation: true
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/cli/cc.py" projects *)'
  - 'Bash(python3 ${CLAUDE_PLUGIN_ROOT}/cli/cc.py projects *)'
---

# All Claude Code projects

Run: `python3 "${CLAUDE_PLUGIN_ROOT}/cli/cc.py" projects "${CLAUDE_PROJECT_DIR}" <command>`

Run that line verbatim, one command per Bash call. Only that exact text is
pre-approved; any variation prompts the user. Relay the output as is: it is
already Markdown.

| Intent | `<command>` |
|--------|-------------|
| List every project | *(omit)* |
| Preview a nuke | `nuke <name>` |
| Confirm a nuke | `nuke <name> --confirm` |
| Open a project's folder | `browse <name>` |

The user's words are intent, not syntax: map them onto this table.

Resolve the user's phrase to exactly one project from the list, then pass a
distinguishing substring (usually the folder name) as `<name>`. If several
projects fit, show them and ask which. Projects shown as **orphaned** (the
folder is gone) or **empty** are the usual nuke targets.

`nuke <name>` is a preview of everything it would remove. Relay it and end your
turn. Run the `--confirm` form only after the user approves that preview.
