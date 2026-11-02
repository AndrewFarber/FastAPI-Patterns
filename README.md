# FastAPI Patterns

An Obsidian vault of FastAPI design patterns, also usable as a Claude Code skill (`SKILL.md`).

## Layout
- `patterns/<topic>/`: the notes. Each topic folder has a `0-<topic>-guide` note listing its notes.
- `examples/<topic>/`: the runnable, tested code that the notes show.
- `INDEX.md`: every topic and note, for Claude.

## Note names
`<section><letter>-<topic>-<name>`, e.g. `2b-settings-db`. A note for a specific capability keeps the general note's prefix and extends its name: `2b-settings-db-iam-auth`.

## Examples
Code blocks whose first line is a full path (`# app/config/db.py`) are copies of files in `examples/<topic>/`. Edit the file, never the block, then sync:

```bash
nix run .#sync      # copy example code into the notes
nix run .#test      # run every topic's tests, including a check that the notes are in sync
nix develop         # shell with Python, uv, and Node; then e.g. `cd examples && uv run pytest settings`
```

Python packages are pinned in `examples/uv.lock`; Nix provides Python, uv, Node (for AWS CDK), and git.
