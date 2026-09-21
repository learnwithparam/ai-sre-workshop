"""Build the contents page of a teaching surface from the sections it has.

This was a sticky schedule rail beside the text. A book has one contents and it
sits at the front, so it is there when the book is printed and a facilitator
holding paper can still find Module 4.

Generated, because a hand-written list of links is a list that will point at a
section somebody renamed. tests/test_contents.py fails when a page carries a
contents other than the one its own sections would produce.

    python scripts/contents.py        rewrites every surface in place
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURFACES = ("guide.html", "workbook.html")
OPEN = '<nav class="contents" aria-label="Contents">'
CLOSE = "</nav>"

SECTION = re.compile(
    r'<section class="(?:before|segment|chapter)[^"]*" id="([^"]+)"[^>]*>(.*?)</section>', re.S
)
LABEL = re.compile(r'<p class="(?:when|kicker)">(.*?)</p>', re.S)
HEADING = re.compile(r"<h2>(.*?)</h2>", re.S)


def sections(page: str) -> list[tuple[str, str, str]]:
    """Every section a reader meets, as (id, label, title)."""
    found = []
    for anchor, body in SECTION.findall(page):
        label = LABEL.search(body)
        heading = HEADING.search(body)
        if heading is None:
            continue
        title = re.sub(r"<[^>]+>", "", heading.group(1)).strip()
        found.append((anchor, re.sub(r"<[^>]+>", "", label.group(1)).strip() if label else "", title))
    return found


def contents(entries: list[tuple[str, str, str]]) -> str:
    rows = "\n".join(
        f'<li><span class="no">{index + 1:02d}</span>'
        f'<a href="#{anchor}">{title}<span class="what">{label}</span></a></li>'
        for index, (anchor, label, title) in enumerate(entries)
    )
    return f"{OPEN}\n<h2>Contents</h2>\n<ol>\n{rows}\n</ol>\n{CLOSE}"


def rewrite(path: Path) -> int:
    page = path.read_text()
    built = contents(sections(page))
    start = page.find(OPEN)
    if start == -1:
        raise SystemExit(f"{path.name} has no contents to fill; add the shell first")
    end = page.find(CLOSE, start) + len(CLOSE)
    path.write_text(page[:start] + built + page[end:])
    return len(sections(page))


if __name__ == "__main__":
    for name in SURFACES:
        path = ROOT / name
        if path.exists():
            print(f"{name}: {rewrite(path)} sections", file=sys.stderr)
