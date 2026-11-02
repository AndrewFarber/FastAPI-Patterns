---
name: fastapi-patterns
description: Curated FastAPI design patterns and anti-patterns. Use when designing, writing, refactoring, or reviewing Python FastAPI code.
---

# FastAPI Patterns

## Finding patterns
1. Read `INDEX.md` and pick the topics that match the task.
2. Open each topic's guide (`0-<topic>-guide.md`, or the topic's single note) and pick the notes that match. Open only those notes; don't load the whole vault.
3. `[[some-note]]` is an Obsidian wikilink to `some-note.md` somewhere under `patterns/`. Find it by filename.
4. Ignore `TODO.md`. It is the author's planning list, not pattern content.
5. A code block whose first line is a full path (`# app/config/db.py`, `# infra/database_stack.py`) is a copy of a tested file in `examples/<topic>/`. Read `examples/` only when a note's code isn't enough. Blocks with short paths (`# main.py`) are fragments.

## Choosing between patterns
When a pattern note offers several options (e.g. three ways to access settings):
1. Answer what you can from the codebase first (dependencies, existing `config/`, `main.py`, deployment files).
2. Ask the user only the remaining questions: at most four at a time, recommended option first, using the AskUserQuestion tool when available.
3. If the user doesn't know or doesn't care, use the option the note recommends and say so.
4. Summarize the decisions in one short list before writing code.

Skip the questions when the user's request already settles them, or when the change is small and doesn't touch a decision (e.g. adding one field to an existing settings model).
