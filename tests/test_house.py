"""The workshop brand, as this repository holds it.

design/BRAND.md says what each value is for. These assertions name the value rather than
checking a token merely exists, because a token with the wrong value passes a test that
only counts tokens. The contrast ratios are computed, not trusted from a note.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from tokens import MINIMUM_RATIO, contrast_ratio, render_css, tokens  # noqa: E402

T = tokens()
PAGES = ("workbook.html", "guide.html")
STYLE = ROOT / "design/book.css"

BRAND = {
    "paper": "#FAFAFA",
    "card": "#FFFFFF",
    "ink": "#151515",
    "ink-2": "#414141",
    "muted": "#606060",
    "faint": "#808080",
    "line": "#DFDFDF",
    "accent": "#FAFF69",
    "accent-deep": "#4F5101",
    "fill-dark": "#1F1F1C",
    "pass": "#008138",
    "fail": "#BF000F",
    "wait": "#B75000",
}


def test_every_brand_token_carries_its_sampled_value():
    wrong = [
        f"{n} is {T['color'].get(n, {}).get('value')}, expected {v}"
        for n, v in BRAND.items()
        if T["color"].get(n, {}).get("value") != v
    ]
    assert wrong == []
    assert sorted(T["color"]) == sorted(BRAND), "a token was added or removed without changing the brand"


def test_every_declared_contrast_pair_reaches_the_level_it_claims():
    failures = []
    for pair in T["contrast"]["pairs"]:
        ratio = contrast_ratio(T["color"][pair["fg"]]["value"], T["color"][pair["bg"]]["value"])
        if ratio < MINIMUM_RATIO[pair["level"]]:
            need = MINIMUM_RATIO[pair["level"]]
            failures.append(f"{pair['fg']} on {pair['bg']} is {ratio:.2f}, needs {need} for {pair['level']}")
    assert failures == []


def test_every_text_state_and_fill_colour_has_a_contrast_pair():
    # A colour that renders words and appears in no pair is one nobody checked. A border is
    # exempt through its role. A surface or a fill is judged as the background words sit on.
    pairs = T["contrast"]["pairs"]
    foreground = {p["fg"] for p in pairs}
    background = {p["bg"] for p in pairs}
    unchecked = [
        name
        for name, token in T["color"].items()
        if token["role"] != "border"
        and name not in (background if token["role"] in ("surface", "fill") else foreground)
    ]
    assert unchecked == []


def test_the_yellow_is_a_fill_and_never_the_colour_of_words():
    # It is 1.03 to 1 against the paper. No pair may put it in front of anything.
    assert [p for p in T["contrast"]["pairs"] if p["fg"] == "accent"] == []
    assert T["color"]["accent"]["role"] == "fill"


def test_the_generated_stylesheet_matches_the_token_source():
    for surface in T["surfaces"]:
        path = ROOT / surface["out"]
        assert path.exists(), f"{surface['out']} was never generated, run make tokens"
        assert path.read_text() == render_css(T, surface["name"]), (
            f"{surface['out']} is stale, run make tokens"
        )


def test_no_page_carries_a_dark_palette():
    dark = [
        f
        for f in (*PAGES, "design/book.css")
        if (ROOT / f).exists() and re.search(r"prefers-color-scheme|data-theme", (ROOT / f).read_text())
    ]
    assert dark == []


def test_no_page_pulls_a_font_over_the_network():
    # A document that needs the network to look right looks wrong in a room with bad
    # wifi. The two typefaces are files in design/fonts and nothing else.
    pattern = r"fonts\.googleapis|fonts\.gstatic|url\(\s*[\"']?https?:"
    remote = [
        f
        for f in (*PAGES, "design/book.css")
        if (ROOT / f).exists() and re.search(pattern, (ROOT / f).read_text())
    ]
    assert remote == []


def test_no_stylesheet_writes_a_colour_that_is_not_a_token():
    # A hex in the stylesheet is a second source of truth. The @page margin boxes are the
    # one exception: they sit outside :root and cannot read a variable.
    if not STYLE.exists():
        return
    css = re.sub(r"@page[^{]*\{(?:[^{}]|\{[^}]*\})*\}", "", STYLE.read_text())
    known = {v.lower() for v in BRAND.values()}
    assert [h for h in re.findall(r"#[0-9a-fA-F]{6}\b", css) if h.lower() not in known] == []


def test_the_typefaces_are_inter_and_inconsolata_and_there_is_no_serif():
    assert T["font"]["sans"]["value"].startswith("Inter,")
    assert T["font"]["mono"]["value"].startswith("Inconsolata,")
    assert sorted(T["font"]) == ["mono", "sans"]


def test_the_page_is_one_column_with_no_side_gutter():
    # A side column held a figure number and one short note and pushed the text into a ribbon.
    assert sorted(T["page"]) == ["$comment", "canvas", "width"]
    assert not re.search(r"page-(side|gap|main)", STYLE.read_text())
