"""Phase 8: teach.html is complete, every command in it is real, and its figures are measured."""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEACH = ROOT / "teach.html"
REPORT = ROOT / "evidence/e2e-report.json"
sys.path.insert(0, str(ROOT / "scripts"))
from check_prose import violations  # noqa: E402

MODULES = {"1", "2", "3", "4", "5"}
PARTS = {"goal", "talk", "command", "expect", "question"}
FIGURES = {"tool_calls", "tokens", "cost_usd", "time_to_root_cause_s"}


class Segments(HTMLParser):
    """Collects data-part names per data-module, and the text of every data-figure element."""

    def __init__(self):
        super().__init__()
        self.modules: dict[str, set[str]] = {}
        self.figures: dict[str, str] = {}
        self._stack: list[tuple[str, str | None, str | None]] = []
        self._figure: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        module = a.get("data-module") or (self._stack[-1][1] if self._stack else None)
        self._stack.append((tag, module, a.get("data-figure")))
        if module and a.get("data-part"):
            self.modules.setdefault(module, set()).add(a["data-part"])
        if a.get("data-module"):
            self.modules.setdefault(a["data-module"], set())
        if a.get("data-figure"):
            self._figure = a["data-figure"]
            self.figures[self._figure] = ""

    def handle_endtag(self, tag):
        while self._stack:
            popped = self._stack.pop()
            if popped[2]:
                self._figure = None
            if popped[0] == tag:
                break

    def handle_data(self, data):
        if self._figure:
            self.figures[self._figure] += data


def parsed() -> Segments:
    parser = Segments()
    parser.feed(TEACH.read_text())
    return parser


def test_teach_exists():
    assert TEACH.exists() and "<title>" in TEACH.read_text()


def test_named_targets_and_files_exist():
    text = TEACH.read_text()
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", (ROOT / "Makefile").read_text(), flags=re.M))
    named = set(re.findall(r"\bmake ([a-z][a-z0-9-]*)", text))
    assert named, "teach.html names no make targets"
    assert named <= targets, f"unknown targets: {named - targets}"
    files = set(re.findall(r'data-file="([^"]+)"', text))
    assert files, "teach.html cites no files"
    assert [f for f in files if not (ROOT / f).exists()] == []


def test_every_module_segment_is_complete():
    modules = parsed().modules
    assert MODULES <= set(modules)
    incomplete = {m: sorted(PARTS - modules[m]) for m in MODULES if not PARTS <= modules[m]}
    assert incomplete == {}


def test_figures_match_e2e_report():
    report = json.loads(REPORT.read_text())
    figures = parsed().figures
    assert FIGURES <= set(figures)
    for key in FIGURES:
        assert figures[key].strip() == str(report["bad_release"][key]), key


def test_prose_is_clean():
    for name in ("teach.html", "README.md", "AGENTS.md"):
        assert violations((ROOT / name).read_text()) == [], name
