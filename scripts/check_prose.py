"""Fail on em or en dashes and filler words in learner-facing prose.

The word lists are scripts/prose-rules.json, a committed copy of learnwithparam's house rules
(rules 3 and 5), so CI can run them without the author's machine.

    check_prose.py                 every tracked markdown and HTML file
    check_prose.py FILE [FILE...]  only those

With no arguments it checks everything tracked, which is what `make check` runs. It used to
take a list of three named files, and a rule that only fires on files someone remembered to
list is a rule that stops firing: workbook.html was written and checked by nothing.
"""

import json
import re
import subprocess
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DASHES = {"—": "em dash", "–": "en dash"}
RULES_FILE = ROOT / "scripts/prose-rules.json"
HOUSE_RULES = Path.home() / ".claude/skills/lwp-shared/scripts/house_rules.py"
RULES = json.loads(RULES_FILE.read_text())
WORDS = RULES["words"]
PHRASES = RULES["phrases"]


def rules_stale() -> str | None:
    """The lists are a committed copy of the house rules. Where the rules live, prove the copy matches.

    CI has no home directory, so this passes there: drift is caught on a developer machine only.
    """
    if not HOUSE_RULES.exists():
        print("prose rules: not compared with the house rules, none on this machine")
        return None
    current = subprocess.run(
        [sys.executable, str(HOUSE_RULES), "--vendor"], capture_output=True, text=True, check=True
    ).stdout
    if json.loads(current) == RULES:
        return None
    name = RULES_FILE.relative_to(ROOT)
    return f"{name} is out of date: run house_rules.py --vendor > {name}"


def violations(text: str) -> list[str]:
    found = []
    for lineno, line in enumerate(unescape(text).splitlines(), 1):
        lower = line.lower()
        found += [f"{lineno}: {name}" for char, name in DASHES.items() if char in line]
        found += [f"{lineno}: '{w}'" for w in WORDS if re.search(rf"\b{re.escape(w)}\b", lower)]
        found += [f"{lineno}: '{p}'" for p in PHRASES if p in lower]
    return found


def tracked() -> list[str]:
    """Every tracked or untracked-but-not-ignored prose file, as git sees it."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    return [
        str(ROOT / name) for name in listed if name.endswith((".md", ".html")) and (ROOT / name).is_file()
    ]


def main(paths: list[str]) -> int:
    paths = paths or tracked()
    failed = 0
    stale = rules_stale()
    if stale:
        print(stale)
        failed = 1
    for path in paths:
        for v in violations(Path(path).read_text()):
            print(f"{path}:{v}")
            failed = 1
    if not failed:
        print(f"prose clean: {len(paths)} files")
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
