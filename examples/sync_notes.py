"""Copy example files into the code blocks of the notes that show them.

A note's code block is synced when its first line is exactly "# <path>",
where <path> ends in .py (a python block) or is Dockerfile (a dockerfile block),
and examples/<topic>/<path> is a file. <topic> is the note's folder
(patterns/settings/... -> examples/settings/...).

A block that shows only part of a file says so on its first line,
"# main.py (fragment)", and is left alone. A bare "# <path>" that doesn't
resolve is an error: a typo or a moved file would otherwise turn a synced
block into an unchecked one.

Edit code in examples/, never in a synced block: this script overwrites them.

    python sync_notes.py           rewrite out-of-date notes
    python sync_notes.py --check   list out-of-date notes and exit 1 (used by the tests)
"""

import re
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent
PATTERNS = EXAMPLES.parent / "patterns"
BLOCK = re.compile(
    r"^```(?P<lang>python|dockerfile)\n# (?P<path>[\w./-]+\.py|(?:[\w./-]+/)?Dockerfile)\n.*?^```$",
    re.MULTILINE | re.DOTALL,
)


def synced(note: Path, missing: list[str]) -> str:
    topic = EXAMPLES / note.parent.name

    def replace(match: re.Match[str]) -> str:
        source = topic / match["path"]
        if not source.is_file():
            missing.append(f"{note.relative_to(PATTERNS.parent)}: # {match['path']} (label fragments as '(fragment)')")
            return match[0]
        return f"```{match['lang']}\n# {match['path']}\n{source.read_text()}```"

    return BLOCK.sub(replace, note.read_text())


def main() -> int:
    check = "--check" in sys.argv[1:]
    stale, missing = [], []
    for note in sorted(PATTERNS.rglob("*.md")):
        text = synced(note, missing)
        if text != note.read_text():
            stale.append(note.relative_to(PATTERNS.parent))
            if not check:
                note.write_text(text)
    for path in stale:
        print(f"{'out of date' if check else 'updated'}: {path}")
    for line in missing:
        print(f"no such file: {line}")
    return 1 if missing or (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
