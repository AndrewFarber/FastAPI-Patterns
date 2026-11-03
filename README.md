# FastAPI Patterns

An Obsidian vault of FastAPI design patterns, also usable as a Claude Code skill (`SKILL.md`).

## Layout
- `patterns/<topic>/`: the notes. Each topic folder has a `<topic>-guide` note: a table of its notes, one line each.
- `examples/`: one runnable, tested app, `shop-api`, in the domain layout: `app/core/`, `app/shared/`, and one package per domain in `app/services/` (`users`, `orders`). Every topic's notes show it.
- `INDEX.md`: one line per topic, pointing to its guide, for Claude.

## Note names
`<topic>-<name>`, e.g. `settings-db`. A note for a specific capability extends the general note's name: `settings-db-iam-auth`. Order and grouping live in the guide, not in the name.

## Note sections
New notes start from `_templates/pattern.md`: properties `title`, `category`, and `related` (the topic's guide and every note linked in the body; a guide lists every note it links), then **Overview**, **Rules**, and **Code example**.

## Examples
Code blocks whose first line is a full path (`# app/core/config/db.py`) are copies of files in `examples/`. Edit the file, never the block, then sync. `# <path> (fragment)` marks part of an example file, and `# <path> (sketch)` code that is in no example file; sync leaves both alone.

```bash
nix run .#sync      # copy example code into the notes
nix run .#test      # run the example app's tests
nix develop         # shell with Python and uv
```

Python packages are pinned in `examples/uv.lock`; Nix provides Python, uv, ruff, and git.
