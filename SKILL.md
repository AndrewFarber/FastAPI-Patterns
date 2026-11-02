---
name: fastapi-patterns
description: Curated FastAPI patterns and anti-patterns. Use when designing, building, refactoring, or reviewing Python FastAPI code: finds the patterns that fit the feature being built or the existing codebase, and offers to apply them.
---

# FastAPI Patterns

Match the vault's patterns against the work at hand, propose the ones that fit, and implement only what the user picks.

## 1. Understand the work
- **The feature:** what the user is building or changing, in a sentence.
- **The codebase:** look before reading notes. `pyproject.toml` (dependencies), the `app/` layout, `config/`, `main.py`, `tests/conftest.py`, deployment files. Note what already exists, so you don't propose a pattern that's already applied.

## 2. Find candidate patterns
1. Read `INDEX.md`, then the guide of each topic that could matter (`0-<topic>-guide.md`, or the topic's single note). Each guide line names a pattern in one line.
2. Open only the notes whose line could apply. `[[some-note]]` is `some-note.md` somewhere under `patterns/`.
3. In each note, read **Fits when** and **Signals** first:
   - **Feature** signals: does the request say this?
   - **Code** signals: grep the codebase for them (`os.getenv(`, `url: PostgresDsn`, `verify_aud`). A hit with its `file:line` is the evidence.
4. Ignore `TODO.md` and `_templates/`.

## 3. Judge the fit
For each candidate decide one of:
- **Fits the feature:** the feature needs it now.
- **Fits the codebase:** a code signal matched, so existing code would improve; not required for the feature.
- **Already applied**, or **doesn't fit** (a **Not when** bullet matches): drop it, mention it in one line at most.

Prefer few strong matches over many weak ones. A note's indented children (in its guide) only fit if the parent does. If nothing fits, say so and continue without the vault.

## 4. Ask before implementing
Present the matches as a short list, feature fits first:
- the pattern (`[[note]]`), why it fits (the feature need, or `file:line` evidence), and what would change (files, rough size).

Then ask which to implement with AskUserQuestion (`multiSelect: true`, at most four options, recommended first). Don't edit code before the user answers. If the user already said "just do it", implement the feature fits and list the codebase fits as suggestions.

When a chosen note offers options (e.g. three ways to access settings), settle them in the same round: answer what the codebase already decides, ask only the rest, and use the note's recommended option when the user doesn't care.

## 5. Implement
- Follow the note's **Pattern** code and **Rules**, and avoid its **Anti-patterns**. A code block whose first line is a full path (`# app/config/db.py`) is a tested file in `examples/<topic>/`; read the full file there when the block isn't enough. Blocks marked `(fragment)` show part of a file.
- Adapt names to the codebase (`orders-api`, module paths), not the other way round.
- Change only what the chosen patterns need; leave unrelated code as it is.
- Finish with one short list: which patterns were applied, where, and any codebase fits not yet taken.
