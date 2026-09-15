"""Fail on em or en dashes and filler words in learner-facing prose.

The word lists copy learnwithparam's house rules (rules 3 and 5), so CI can run them without
the author's machine. Usage: check_prose.py FILE [FILE...]
"""

import re
import sys
from html import unescape
from pathlib import Path

DASHES = {"—": "em dash", "–": "en dash"}
WORDS = {
    "crucial", "cutting-edge", "delve", "game-changer", "landscape", "leverage", "notably",
    "paradigm", "realm", "revolutionize", "robust", "seamless", "straightforward", "unleash",
}  # fmt: skip
PHRASES = [
    "as an ai", "let's dive in", "in today's world", "buckle up", "here's the thing",
    "the reality is", "it's worth noting", "it's important to note", "it should be noted",
    "at its core", "in the ever-evolving", "without further ado", "a testament to",
    "navigate the complexities", "stands out as", "serves as a",
]  # fmt: skip


def violations(text: str) -> list[str]:
    found = []
    for lineno, line in enumerate(unescape(text).splitlines(), 1):
        lower = line.lower()
        found += [f"{lineno}: {name}" for char, name in DASHES.items() if char in line]
        found += [f"{lineno}: '{w}'" for w in WORDS if re.search(rf"\b{re.escape(w)}\b", lower)]
        found += [f"{lineno}: '{p}'" for p in PHRASES if p in lower]
    return found


def main(paths: list[str]) -> int:
    failed = 0
    for path in paths:
        for v in violations(Path(path).read_text()):
            print(f"{path}:{v}")
            failed = 1
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
