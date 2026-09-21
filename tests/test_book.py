"""The printed book is the same book as the pages, and its text layer works.

A PDF fails silently in a way nothing else here does: every page looks perfect and
the text extracts as gibberish, or the pages are simply last month's. Neither is
visible in a diff. `make book` proves the text layer on its own output, because that
needs a browser and poppler. These are what `make check` can assert with neither, on
a machine that only has the files.
"""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRESHNESS = ROOT / "scripts/pdf_freshness.json"
CSS = ROOT / "design/book.css"
BUILDER = ROOT / "scripts/build_book.mjs"

# Each of these renders perfectly and extracts as garbage. They were isolated one at
# a time, by experiment, and every one is a property somebody would reasonably add
# back for the screen.
TRAPS = {
    "overflow: visible !important": "overflow-x on a command clips it on paper, in the text layer too",
    "letter-spacing: normal !important": "tracking both over-splits and glues runs",
    "font-weight: 700 !important": "a variable face at 900 glues its run and drops a character",
    "position: static !important": "a positioned list item paints last and detaches from its heading",
}


def recorded() -> dict[str, dict[str, str]]:
    return json.loads(FRESHNESS.read_text()) if FRESHNESS.exists() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def test_every_declared_pdf_exists():
    declared = set(re.findall(r'^  "([\w.-]+\.pdf)":', BUILDER.read_text(), flags=re.M))
    assert declared, "the builder declares no PDFs"
    assert sorted(declared) == sorted(recorded()), "run make book"
    missing = [name for name in declared if not (ROOT / name).exists()]
    assert missing == [], f"declared but never built, run make book: {missing}"


def test_no_pdf_is_older_than_anything_it_was_built_from():
    # 🔴 The builder counts as a source. A document and its PDF are both downstream
    # of the script that writes them, so an edit there with no rebuild leaves the
    # pair consistent with each other and both behind.
    #
    # 🔴 Content hashes, never modification times. A fresh checkout gives every file
    # the same timestamp in an arbitrary order, so an mtime gate reports everything
    # stale on its first CI run and could never have passed there.
    stale = []
    for pdf, sources in recorded().items():
        for source, digest in sources.items():
            path = ROOT / source
            if path.exists() and sha256(path) != digest:
                stale.append(f"{pdf} was not rebuilt after {source} changed")
    assert sorted(set(stale)) == [], "run make book"


def test_the_print_block_still_resets_every_trap():
    print_block = CSS.read_text()
    print_block = print_block[print_block.index("@media print") :]
    absent = [f"{rule} ({why})" for rule, why in TRAPS.items() if rule not in print_block]
    assert absent == []


def test_the_page_inset_is_declared_in_one_place():
    # A CSS @page margin overrides the margin passed to page.pdf(), so setting both
    # only hides which one is live. And it must not be padding on a wrapper: block
    # padding insets the start and end of a block, leaving page two flush to the paper.
    css = CSS.read_text()
    assert re.search(r"@page\s*\{[^}]*margin:", css), "@page declares no margin"
    assert 'margin: { top: "0", bottom: "0", left: "0", right: "0" }' in BUILDER.read_text()


def test_the_builder_refuses_a_chromium_without_margin_boxes():
    # Without them the book prints with no page numbers and nothing says so.
    assert "MARGIN_BOXES_FROM = 131" in BUILDER.read_text()
