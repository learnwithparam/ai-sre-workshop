"""The two teaching surfaces hold one copy of each idea, and each points at the other.

workbook.html is the only place an explanation is written. guide.html is the facilitator
guide: it carries the timing, the talk track and the commands for one day, and cites
concepts by id rather than restating them.

These tests are the thing that keeps that true. Without them the workbook becomes a second
copy of the guide, the two disagree, and the room is taught whichever one the facilitator
happened to open.
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPINE = ROOT / "workbook.html"
SHEET = ROOT / "guide.html"
sys.path.insert(0, str(ROOT / "scripts"))
from contents import contents, sections  # noqa: E402

SHINGLE = 12
TAGS = re.compile(r"<(script|style|pre|code)[\s\S]*?</\1>|<[^>]+>")
PUNCTUATION = re.compile(r"[^a-z0-9' ]+")


def declared() -> set[str]:
    """Concept ids the spine declares."""
    return set(re.findall(r'id="c-([a-z0-9-]+)"', SPINE.read_text()))


def cited() -> set[str]:
    """Concept ids the run sheet cites."""
    return set(re.findall(r'data-concept="([a-z0-9-]+)"', SHEET.read_text()))


def prose(text: str) -> list[str]:
    """Visible prose, with markup, code and commands removed."""
    return PUNCTUATION.sub(" ", TAGS.sub(" ", text).lower()).split()


def shingles(text: str) -> set[str]:
    words = prose(text)
    return {" ".join(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def test_the_spine_declares_concepts():
    assert len(declared()) > 0, "workbook.html declares no concept ids"


def test_every_cited_concept_is_declared():
    dangling = sorted(cited() - declared())
    assert dangling == [], f"guide.html cites concepts the workbook does not declare: {dangling}"


def test_every_declared_concept_is_taught():
    # A concept no module covers is an explanation nobody delivers on the day.
    orphans = sorted(declared() - cited())
    assert orphans == [], f"the spine explains what no module cites: {orphans}"


def test_no_prose_is_duplicated_across_the_surfaces():
    # One resolver per concept, applied to writing. An explanation belongs to the
    # spine; the run sheet points at it. Code and commands are exempt.
    shared = sorted(shingles(SPINE.read_text()) & shingles(SHEET.read_text()))
    assert shared[:3] == [], f"{len(shared)} phrase(s) written twice, first: {shared[:3]}"


def test_no_concept_is_declared_twice():
    ids = re.findall(r'id="c-([a-z0-9-]+)"', SPINE.read_text())
    repeated = [name for name, count in Counter(ids).items() if count > 1]
    assert repeated == [], f"declared more than once: {repeated}"


def test_named_targets_and_files_exist():
    # Only code and terminal blocks are scanned. Ordinary prose contains "make sure"
    # and "make your own", and treating those as commands produces a check that
    # cries wolf, which is the fastest way to get a check ignored.
    text = SPINE.read_text()
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", (ROOT / "Makefile").read_text(), flags=re.M))
    blocks = " ".join(m[1] for m in re.findall(r"<(pre|code)\b[^>]*>([\s\S]*?)</\1>", text))
    named = set(re.findall(r"\bmake ([a-z][a-z0-9-]*)", blocks))
    assert named <= targets, f"unknown targets: {named - targets}"
    files = set(re.findall(r'data-file="([^"]+)"', text))
    assert [f for f in files if not (ROOT / f).exists()] == []


def test_every_internal_link_lands_somewhere():
    # A reader who clicks a dead anchor in front of a room does not forgive the page.
    for path in (SPINE, SHEET):
        text = path.read_text()
        dead = [a for a in set(re.findall(r'href="#([^"]+)"', text)) if f'id="{a}"' not in text]
        assert dead == [], f"{path.name} links to anchors that do not exist: {sorted(dead)}"


def test_the_contents_is_the_one_the_sections_would_produce():
    # Generated, because a hand-written list of links is a list that will point at a
    # section somebody renamed.
    for path in (SPINE, SHEET):
        page = path.read_text()
        assert contents(sections(page)) in page, f"{path.name}: run python scripts/contents.py"
