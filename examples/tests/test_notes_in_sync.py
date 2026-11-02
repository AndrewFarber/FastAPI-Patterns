import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1]


def test_notes_match_examples():
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / "sync_notes.py"), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
