"""The house book system, as this repository holds it.

Every standalone document across learnwithparam shares one set of values. The copy in
each repository is a copy, so it drifts, and the drift is always the same shape:
somebody adds a dark palette to one document, or pulls a webfont, or nudges a grey.
Each assertion names the value it expects, because a token with the wrong value passes
every test that only counts tokens.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "teach.css"
SURFACES = ("concepts.html", "teach.html", "teach.css")

HOUSE = {
    "--paper": "#FBFAF8",
    "--card": "#FFFFFF",
    "--sunk": "#F5F2EC",
    "--ink": "#1F1B16",
    "--ink-2": "#3D372F",
    "--muted": "#5F594F",
    "--faint": "#948D80",
    "--rule": "#E6E1D8",
    "--rule-2": "#F0EDE7",
    "--go": "#046C4E",
    "--ask": "#A45B08",
    "--no": "#9E2A16",
}


def root_block() -> str:
    css = CSS.read_text()
    return css[css.index(":root {") : css.index("}", css.index(":root {"))]


def test_every_house_token_carries_its_house_value():
    block = root_block()
    wrong = []
    for name, value in HOUSE.items():
        found = re.search(rf"{re.escape(name)}:\s*([^;]+);", block)
        if found is None:
            wrong.append(f"{name} is not declared")
        elif found.group(1).strip() != value:
            wrong.append(f"{name} is {found.group(1).strip()}, the house value is {value}")
    assert wrong == []


def test_the_local_token_says_it_is_local():
    # Deviating from the house is allowed and has to be stated where somebody
    # copying this file will read it. An undocumented extra token is drift.
    css = CSS.read_text()
    assert "Local to this repository" in css, "--accent deviates from the house and does not say so"


def test_no_surface_carries_a_dark_palette():
    # A toggle on three documents out of twenty was the inconsistency, and it
    # doubled every token. The house is light only.
    dark = [f for f in SURFACES if re.search(r"prefers-color-scheme|data-theme", (ROOT / f).read_text())]
    assert dark == []


def test_no_surface_pulls_a_font_over_the_network():
    # A document that needs the network to look right looks wrong in a room with
    # bad wifi, which is every room.
    pattern = r"fonts\.googleapis|fonts\.gstatic|@font-face|https?://[^\"']*\.(?:woff2?|ttf|otf)"
    remote = [f for f in SURFACES if re.search(pattern, (ROOT / f).read_text())]
    assert remote == []


def test_the_screen_mono_stack_has_no_monaco_and_no_courier_new():
    # The first drift the house checker ever caught. The print block is exempt and
    # says why: ui-monospace is what breaks a text layer, Courier is what fixes it.
    mono = re.search(r"--mono:\s*([^;]+);", root_block()).group(1)
    assert "Monaco" not in mono and "Courier New" not in mono


def test_prose_is_serif_and_furniture_is_not():
    # House rule one. A paragraph is read, so serif; a schedule row, a command block
    # and a table are scanned, so sans. Never a table body in serif.
    css = CSS.read_text()
    screen = css[: css.index("@media print")]
    assert re.search(r"body\s*\{[^}]*font-family:\s*var\(--serif\)", screen), "body is not set in the serif"

    scanned = [
        rule
        for rule in re.findall(r"([^{}]+)\{([^}]*)\}", screen)
        if re.search(r"(^|,)\s*table\s*(,|$)", rule[0].strip())
    ]
    assert scanned, "no rule sets a font on a table"
    assert any("var(--sans)" in body for _, body in scanned), "a table body is not set in the sans"
