# FastAPI Patterns

An Obsidian vault of FastAPI design patterns, also usable as a Claude Code skill (`SKILL.md`).

## Layout
- `patterns/<topic>/`: the notes. Each topic folder has a `0-<topic>-guide` note listing its notes.
- `examples/<topic>/`: the runnable, tested code that the notes show.
- `INDEX.md`: one line per topic, pointing to its guide, for Claude.

## Note names
`<section><letter>-<topic>-<name>`, e.g. `2b-settings-db`. A note for a specific capability keeps the general note's prefix and extends its name: `2b-settings-db-iam-auth`.

## Note sections
New notes start from `_templates/pattern.md`: a one-line pattern, **Fits when**, **Signals** (what in a request or in code calls for it), **Pattern**, **Rules**, **Anti-patterns**. The skill matches **Fits when** and **Signals** against the task and the codebase, so keep code signals greppable.

## Examples
Code blocks whose first line is a full path (`# app/config/db.py`) are copies of files in `examples/<topic>/`. Edit the file, never the block, then sync:

```bash
nix run .#sync      # copy example code into the notes
nix run .#test      # run every topic's tests, including a check that the notes are in sync
nix develop         # shell with Python and uv; then e.g. `cd examples && uv run pytest settings`
```

Python packages are pinned in `examples/uv.lock`; Nix provides Python, uv, ruff, and git.
