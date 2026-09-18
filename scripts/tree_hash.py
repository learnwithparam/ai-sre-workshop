"""Print a hash of the working tree, so a score is never computed from results of older code.

`--all` covers every file. The default leaves out prose (Markdown, teach.html and its test),
because editing the facilitator guide does not invalidate a fifteen-minute e2e run.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# `--all` covers every file. The default leaves out prose and the surfaces around it:
# the stylesheet, the book builder, the PDFs it writes and the tests that read them.
# `make e2e` loads none of them, so none of them can invalidate a fifteen-minute run.
PROSE = (
    "teach.html",
    "concepts.html",
    "teach.css",
    "tests/test_teach.py",
    "tests/test_concepts.py",
    "tests/test_book.py",
    "tests/test_house.py",
    "scripts/build_book.mjs",
    "scripts/contents.py",
    "scripts/pdf_freshness.json",
)


def tree_hash(include_prose: bool) -> str:
    files = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    digest = hashlib.sha256()
    # e2e writes evidence/ itself, so its own stamp cannot include it; the check stamp does.
    measured = ("artifacts/",) if include_prose else ("artifacts/", "evidence/")
    for name in sorted(f for f in files if f and not f.startswith(measured)):
        if not include_prose and (name.endswith((".md", ".pdf")) or name in PROSE):
            continue
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    print(tree_hash(include_prose="--all" in sys.argv))
