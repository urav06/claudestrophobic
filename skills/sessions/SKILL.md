---
name: sessions
description: List and manage sessions in the current project
argument-hint: "[list | delete <name|uuid> | prune --older <duration> | browse]"
disable-model-invocation: true
allowed-tools: Bash
---

# Sessions in this project

Run: `python3 "${CLAUDE_PLUGIN_ROOT}/cli/cc.py" sessions "${CLAUDE_PROJECT_DIR}" <command>`

| Intent | `<command>` |
|--------|-------------|
| List sessions | *(omit)* |
| Delete a session | `delete <uuid-prefix>` |
| Prune old sessions | `prune <duration>` — e.g. `2w`, `3d`, `6m`, `12h` |
| Confirm prune | `prune <duration> --confirm` |
| Open the project folder | `browse` |

To delete by description ("the one about auth"), list first, pick the session,
then pass its **UUID prefix** (the `xxxxxxxx` shown) to `delete`.
Sessions marked ● are active and protected from deletion.

To manage *other* projects, or remove one entirely, use `/projects`.
