"""Every external claim carries a source, and every source is still cited.

An enterprise reader checks the citations, and a link that rotted is a citation
nobody can check. sources.json is the one list; these tests bind it to the pages in
both directions so neither can drift. Reachability is a separate CI job, because a
gate that needs the network cannot sit inside `make check`.
"""

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources.json"
SURFACES = ("workbook.html", "guide.html", "README.md")


def declared() -> list[dict[str, str]]:
    return json.loads(SOURCES.read_text())["sources"]


def cited() -> set[str]:
    found: set[str] = set()
    for name in SURFACES:
        text = (ROOT / name).read_text()
        found |= set(re.findall(r'href="(https?://[^"]+)"', text))
        found |= set(re.findall(r"\]\((https?://[^)]+)\)", text))
    return found


# A link to the repository, an image registry or a vendor whose product the lab runs
# is plumbing rather than a claim about the world. What has to be declared is
# anything a reader would follow to check something the pages assert.
PLUMBING = re.compile(r"https?://(github\.com|hub\.docker\.com|localhost|clickhouse\.com|openrouter\.ai)")


def test_every_cited_url_is_declared():
    known = {source["url"] for source in declared()}
    undeclared = sorted(url for url in cited() - known if not PLUMBING.match(url))
    assert undeclared == [], f"cited but not in sources.json: {undeclared}"


def test_every_declared_source_is_cited():
    # A source nothing points at is a reading list pretending to be a citation.
    orphans = sorted({source["url"] for source in declared()} - cited())
    assert orphans == [], f"declared but cited nowhere: {orphans}"


def test_every_source_says_what_it_supports_and_when_it_was_read():
    incomplete = [
        source.get("url", "?")
        for source in declared()
        if not all(source.get(field) for field in ("url", "title", "publisher", "read", "supports"))
    ]
    assert incomplete == []


def test_no_source_was_read_in_the_future():
    # A date typed rather than checked is the first sign nobody opened the page.
    ahead = [s["url"] for s in declared() if date.fromisoformat(s["read"]) > date.today()]
    assert ahead == []
