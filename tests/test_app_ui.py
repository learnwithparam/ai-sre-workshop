"""The signup page keeps the hooks its drivers use, and stays labelled and self-consistent.

The browser load generator, the e2e specs and the page's own script all address this template by
id, by label and by visible text. A redesign that renames one of them breaks traffic or a spec
minutes into a run, so the contract is asserted here, without Docker.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "subscription-app/templates/index.html"
LOCUSTFILE = ROOT / "load-generator/locustfile.py"
CONTROLS = {"input", "select", "textarea"}


class Page(HTMLParser):
    """Ids, label targets, form controls and the direct text of every element."""

    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.labels: dict[str, str] = {}  # for= -> label text
        self.controls: list[tuple[str, str | None]] = []
        self.texts: list[str] = []
        self.inline_styles: list[str] = []
        self._stack: list[list[str]] = []
        self._label_for: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if element_id := a.get("id"):
            self.ids.add(element_id)
        if a.get("style"):
            self.inline_styles.append(tag)
        if tag in CONTROLS:
            self.controls.append((tag, a.get("id")))
        if tag == "label":
            self._label_for = a.get("for")
            self.labels[a.get("for") or ""] = ""
        if tag not in ("br", "img", "input", "meta", "link"):
            self._stack.append([])

    def handle_endtag(self, tag):
        if not self._stack:
            return
        text = " ".join(" ".join(self._stack.pop()).split())
        if text:
            self.texts.append(text)
        if tag == "label" and self._label_for is not None:
            self.labels[self._label_for] = text
            self._label_for = None

    def handle_data(self, data):
        # Playwright's text engine ignores script and style, so the button label inside the
        # page script is not a second match for it.
        if self._stack and data.strip() and self.lasttag not in ("script", "style"):
            self._stack[-1].append(data.strip())


def page() -> Page:
    parser = Page()
    parser.feed(TEMPLATE.read_text())
    return parser


def elements_with(text: str) -> list[str]:
    """Elements whose own text carries `text`, the way Playwright's text= engine matches."""
    return [t for t in page().texts if text.lower() in t.lower()]


def locust_selectors() -> tuple[set[str], set[str], set[str]]:
    source = LOCUSTFILE.read_text()
    ids = set(re.findall(r'(?:locator|browse_page)\(\s*(?:page,\s*)?["\']#([\w-]+)["\']', source))
    texts = set(re.findall(r'consume_page\(page,\s*["\'](.+?)["\']\)', source))
    texts |= set(re.findall(r'locator\("text=(.+?)"\)', source))
    labels = set(re.findall(r'get_by_label\("(.+?)"\)', source))
    return ids, texts, labels


def test_ids_the_load_generator_drives_exist():
    ids, _, _ = locust_selectors()
    assert ids, "no ids parsed from the load generator"
    assert sorted(ids - page().ids) == []


def test_text_the_load_generator_scrolls_to_is_present_once():
    _, texts, _ = locust_selectors()
    assert texts, "no text selectors parsed from the load generator"
    # Playwright is strict: two elements carrying the same text fail the click, not the assertion.
    assert {t: len(elements_with(t)) for t in texts} == dict.fromkeys(texts, 1)


def test_every_control_is_labelled():
    parsed = page()
    unlabelled = [tag for tag, cid in parsed.controls if cid not in parsed.labels]
    assert unlabelled == []
    dangling = [target for target in parsed.labels if target not in parsed.ids]
    assert dangling == []


def test_labels_match_what_the_drivers_ask_for():
    _, _, labels = locust_selectors()
    spec = (ROOT / "e2e/specs/03-app.spec.ts").read_text()
    labels |= set(re.findall(r'getByLabel\("(.+?)"\)', spec))
    texts = list(page().labels.values())
    for wanted in labels:
        matches = [t for t in texts if wanted.lower() in t.lower()]
        assert len(matches) == 1, f"{wanted!r} matches {matches}"


def test_the_page_script_addresses_ids_that_exist():
    used = set(re.findall(r"getElementById\('([\w-]+)'\)", TEMPLATE.read_text()))
    assert used and sorted(used - page().ids) == []


def test_styling_stays_in_the_stylesheet():
    assert page().inline_styles == []
    assert 'href="css/clickhouse_css.css"' in TEMPLATE.read_text()


def test_the_page_declares_a_viewport():
    assert 'name="viewport"' in TEMPLATE.read_text()
