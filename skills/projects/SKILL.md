---
name: projects
description: List every Claude Code project; delete the orphaned ones
argument-hint: "[list | delete <name|orphaned|dormant> | browse <name>]"
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
| Preview a delete | `delete <name>` |
| Confirm a delete | `delete <name> --confirm` |
| Open a project's folder | `browse <name>` |

The user's words are intent, not syntax: map them onto this table.

`<name>` is a project exactly as listed, or its trailing path components
(`kit-ctf`, `code/kit-ctf`). If several projects fit, show them and ask which.

`<name>` can also be a state, which selects every project in it:

- **orphaned**: its folder is gone, so nothing Claude Code kept for it is used
  again. These are the usual delete targets.
- **dormant**: its folder exists but no sessions do. Its memory still loads the
  next time Claude runs there, so delete one only when the user names it or
  asks for dormant projects by that word.

`delete` without `--confirm` is a preview of everything it would remove. Relay
it and end your turn. Run the `--confirm` form only after the user approves that
preview.
