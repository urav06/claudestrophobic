---
name: sessions
description: List and manage sessions in the current project
argument-hint: "[list | delete <name|uuid> | prune --older <duration> | browse]"
disable-model-invocation: true
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/cli/cc.py" sessions *)'
  - 'Bash(python3 ${CLAUDE_PLUGIN_ROOT}/cli/cc.py sessions *)'
---

# Sessions in this project

Run: `python3 "${CLAUDE_PLUGIN_ROOT}/cli/cc.py" sessions "${CLAUDE_PROJECT_DIR}" <command>`

Run that line verbatim, one command per Bash call. Only that exact text is
pre-approved; any variation prompts the user. Relay the output as is: it is
already Markdown.

| Intent | `<command>` |
|--------|-------------|
| List sessions | *(omit)* |
| Delete a session | `delete <uuid-prefix>` |
| Preview a delete | `delete <uuid-prefix> --preview` |
| Preview a prune | `prune <duration>`, such as `2w`, `3d`, `6m`, `12h` |
| Confirm prune | `prune <duration> --confirm` |
| Open the project folder | `browse` |

The user's words are intent, not syntax: map them onto this table. "Preview",
"check first", "what would this remove", or any flag that means the same all
select the preview row.

To delete by description ("the one about auth"), list first, match the phrase
to exactly one session, then pass its **UUID prefix** (the `xxxxxxxx` shown) to
`delete`. If several sessions fit, show them and ask which.

`prune <duration>` is a preview. Relay it and end your turn. Run the
`--confirm` form only after the user approves that preview.

To manage *other* projects, or remove one entirely, use `/projects`.
