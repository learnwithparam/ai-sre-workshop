"""Every picture in the workbook and the guide is drawn by scripts/diagram.mjs, and stays readable.

Five things can quietly go wrong with a hand-drawn diagram, and each is a test here:
the drawing drifts from its description, a label prints too small to read, a colour
is written as a hex instead of a token, a class has no style behind it, and a concept
that deserves a picture has none.
"""

import html as _html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["workbook.html", "guide.html"]
SPECS = ROOT / "design/diagrams"
EXEMPT = SPECS / "exempt.json"
CSS = (ROOT / "design/book.css").read_text()

PRINT_WIDTH_PT = 174 / 25.4 * 72  # the text block on paper, 174 mm
MIN_PRINT_PT = 7.5

FIGURE = re.compile(r'<figure class="diagram" data-diagram="([a-z0-9-]+)">[\s\S]*?</figure>')


def figures() -> list[tuple[str, str, str]]:
    """Every (page, id, html) figure the pages carry."""
    found = []
    for name in PAGES:
        text = (ROOT / name).read_text()
        found += [(name, m.group(1), m.group(0)) for m in FIGURE.finditer(text)]
    return found


def specs() -> set[str]:
    return {p.stem for p in SPECS.glob("*.json") if p.name != "exempt.json"}


def concept_blocks() -> dict[str, str]:
    """Each concept the workbook declares, with the markup inside it."""
    text = (ROOT / "workbook.html").read_text()
    starts = list(re.finditer(r'<div class="concept" id="c-([a-z0-9-]+)"', text))
    blocks = {}
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        blocks[m.group(1)] = text[m.start() : end].split("</section>")[0]
    return blocks


def exempt() -> dict[str, str]:
    return json.loads(EXEMPT.read_text()) if EXEMPT.exists() else {}


def test_the_pages_carry_figures():
    assert len(figures()) > 0, "no page places a figure, so no gate below has anything to check"


def test_every_figure_is_what_the_tool_draws():
    run = subprocess.run(["node", "scripts/diagram.mjs", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr or run.stdout


def test_every_description_is_placed_once_and_every_placement_has_one():
    placed = [i for _, i, _ in figures()]
    repeated = sorted({i for i in placed if placed.count(i) > 1})
    assert repeated == [], f"a diagram is placed twice, its number would repeat: {repeated}"
    assert sorted(set(placed) - specs()) == [], "a page places a diagram with no design/diagrams/<id>.json"
    assert sorted(specs() - set(placed)) == [], "a design/diagrams/<id>.json that no page places"


def test_no_label_prints_smaller_than_the_minimum():
    # A unit on the 504 wide canvas prints at PRINT_WIDTH_PT / 504 points, so size 8.5 lands near 8.3pt.
    # The old canvas was 1010 wide, which is how labels reached 5.5pt.
    small = []
    for page, ident, html in figures():
        width = float(re.search(r'viewBox="0 0 ([0-9.]+) ', html).group(1))
        for size in re.findall(r'<text [^>]*font-size="([0-9.]+)"', html):
            printed = float(size) * PRINT_WIDTH_PT / width
            if printed < MIN_PRINT_PT:
                small.append(f"{page} {ident}: size {size} on a {width:g} canvas prints at {printed:.1f}pt")
    assert small == [], small


def test_every_text_element_carries_its_size():
    bare = [
        f"{p} {i}"
        for p, i, html in figures()
        for tag in re.findall(r"<text [^>]*>", html)
        if "font-size=" not in tag
    ]
    assert bare == [], f"text with no size cannot be measured against the minimum: {bare}"


def test_a_figure_holds_no_literal_colour():
    bad = []
    for page, ident, html in figures():
        if re.search(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|rgba?\(|style=", html):
            bad.append(f"{page} {ident}: a colour or a style written into the figure")
        if re.search(r'\b(fill|stroke)="(?!none")', html):
            bad.append(f"{page} {ident}: fill or stroke set by attribute, use a token class")
    assert bad == [], bad


def test_every_class_a_figure_uses_has_a_style():
    used = {
        c for _, _, html in figures() for attr in re.findall(r'class="([^"]+)"', html) for c in attr.split()
    }
    missing = sorted(c for c in used if not re.search(rf"\.{re.escape(c)}(?![A-Za-z0-9_-])", CSS))
    assert missing == [], f"classes the tool emits that design/book.css does not style: {missing}"


def test_every_concept_has_a_diagram_or_a_written_reason():
    blocks = concept_blocks()
    bare = sorted(i for i, html in blocks.items() if 'class="diagram"' not in html)
    excused = exempt()
    unexplained = sorted(set(bare) - set(excused))
    assert unexplained == [], (
        f"concepts with no diagram and no reason in design/diagrams/exempt.json: {unexplained}"
    )
    stale = sorted(i for i in excused if i not in bare)
    assert stale == [], f"exemptions for concepts that now have a diagram, or do not exist: {stale}"
    thin = sorted(i for i, why in excused.items() if len(why.split()) < 6)
    assert thin == [], f"an exemption needs a sentence saying why a picture would not teach it: {thin}"


def test_a_workbook_figure_travels_with_its_heading():
    # A heading left at the foot of one page and its picture at the top of the next reads as a mistake.
    # Chromium does not honour break-after on a grid item, so the heading, the hook and the first
    # picture sit in one block that cannot split.
    loose = [
        cid
        for cid, html in concept_blocks().items()
        if 'data-diagram="' in html
        and not re.search(
            r'<div class="lead">\s*<h3>[^\n]*</h3>\s*(?:<p class="hook">[^\n]*</p>\s*)?'
            r'<figure class="diagram"',
            html,
        )
    ]
    assert loose == [], f"a concept whose first figure is not held with its heading in a div.lead: {loose}"


# The budget: a figure is a picture, not paragraphs in rectangles ----------------------------


def node(code: str) -> str:
    run = subprocess.run(
        ["node", "--input-type=module", "-e", f'import * as d from "./scripts/diagram.mjs"; {code}'],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    return run.stdout


def problems(spec: dict) -> list[str]:
    return json.loads(node(f"console.log(JSON.stringify(d.problems('t', {json.dumps(spec)})))"))


def test_every_figure_is_inside_the_word_budget_and_has_geometry():
    run = subprocess.run(["node", "scripts/diagram.mjs", "--audit"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


def test_a_label_over_six_words_is_refused():
    spec = {"shape": "flow", "steps": [{"title": "Nobody adds a field at three in the morning"}]}
    assert any("9 words" in p for p in problems(spec))


def test_a_figure_over_thirty_four_words_is_refused():
    steps = [{"title": "one two three four five six"}] * 6
    assert any("words drawn" in p for p in problems({"shape": "flow", "steps": steps}))


def test_a_footnote_under_a_figure_is_refused():
    assert any(
        "foot" in p for p in problems({"shape": "flow", "steps": [{"title": "A"}], "foot": ["Anything"]})
    )


def test_a_list_of_sentences_in_a_box_is_refused():
    assert any(
        "note" in p for p in problems({"shape": "flow", "steps": [{"title": "A", "note": ["one", "two"]}]})
    )


def test_a_split_with_no_arrow_is_refused_and_with_one_is_allowed():
    sides = {"left": {"title": "A", "items": ["x"]}, "right": {"title": "B", "items": ["y"]}}
    assert any("split" in p for p in problems({"shape": "split", **sides}))
    assert problems({"shape": "split", "arrow": "then", **sides}) == []


SHAPES = {
    "gate": {
        "shape": "gate",
        "path": [{"title": "Proposal"}, {"title": "Cited"}, {"title": "Stored"}],
        "gates": [{"after": 0, "refuse": "No trace id"}],
    },
    "growth": {
        "shape": "growth",
        "rising": {"label": "Piling on"},
        "flat": {"label": "Routing"},
        "xlabel": "Mistakes fixed",
        "ylabel": "Prompt size",
        "mark": {"at": 0.6, "label": "Accuracy falls"},
    },
    "scope": {
        "shape": "scope",
        "rings": [
            {"title": "The host", "items": ["files", "network"]},
            {"title": "The agent can read"},
            {"title": "It can change", "tone": "mark"},
        ],
    },
    "pair": {
        "shape": "pair",
        "left": {"title": "Before"},
        "right": {"title": "After", "tone": "mark"},
        "rows": [
            {"label": "Errors", "left": "Rising", "right": "Flat", "changed": True},
            {"label": "Traffic", "left": "Normal", "right": "Normal"},
        ],
    },
}


def test_each_new_shape_draws_and_keeps_its_labels_readable():
    for name, spec in SHAPES.items():
        svg = node(f"console.log(d.drawSvg('t', {json.dumps({**spec, 'alt': 'a picture'})}))")
        width = int(re.search(r'viewBox="0 0 (\d+) ', svg).group(1))
        sizes = [float(s) for s in re.findall(r'font-size="([\d.]+)"', svg)]
        assert sizes, f"{name} drew no text"
        assert min(sizes) * PRINT_WIDTH_PT / width >= MIN_PRINT_PT, f"{name} prints a label too small"
        assert not re.search(r'x="-|y="-|x="(?:5\d\d|[6-9]\d\d)\.', svg), f"{name} draws outside its canvas"


# Prose does not restate its picture ------------------------------------------------------------


def _text(markup: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", " ", markup))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _phrases(text: str, n: int = 6) -> set[str]:
    ws = _words(text)
    return {" ".join(ws[i : i + n]) for i in range(len(ws) - n + 1)}


def _parts(block: str) -> dict[str, str]:
    """What a concept says in each place: heading, hook, captions, body and what its figures draw."""
    figs = [m.group(0) for m in FIGURE.finditer(block)]
    drawn = " ".join(t for f in figs for t in re.findall(r"<text[^>]*>([^<]*)</text>", f))
    captions = re.findall(r"<figcaption>([\s\S]*?)</figcaption>", block)
    return {
        "heading": _text(re.search(r"<h3>(.*?)</h3>", block).group(1)),
        "hook": _text(" ".join(re.findall(r'<p class="hook">(.*?)</p>', block))),
        "captions": _text(" ".join(captions)),
        "body": _text(" ".join(re.findall(r'<div class="body">([\s\S]*?)</div>', block))),
        "drawn": _text(drawn),
    }


def _overlap(body: str, picture: str) -> float:
    """The share of the body's distinct longer words that the picture also uses."""
    mine = {w for w in _words(body) if len(w) >= 4}
    return len(mine & set(_words(picture))) / len(mine) if mine else 0.0


MAX_OVERLAP = 0.45
MAX_PROSE_RUN = 120


def test_a_body_does_not_reuse_the_words_of_its_own_picture():
    over = {}
    for cid, block in concept_blocks().items():
        p = _parts(block)
        share = _overlap(p["body"], p["drawn"] + " " + p["captions"])
        if share >= MAX_OVERLAP:
            over[cid] = round(share, 2)
    assert over == {}, f"bodies that mostly restate their figure, so the picture says nothing new: {over}"


def test_no_six_word_phrase_is_said_twice_in_one_concept():
    repeated = {}
    for cid, block in concept_blocks().items():
        p = _parts(block)
        said = {k: _phrases(v) for k, v in p.items() if k != "drawn"}
        said["drawn"] = _phrases(p["drawn"])
        keys = list(said)
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                if said[a] & said[b]:
                    repeated.setdefault(cid, []).append(f"{a} and {b}: {sorted(said[a] & said[b])[0]!r}")
    assert repeated == {}, f"the same thing stated in two places: {repeated}"


def test_no_run_of_prose_is_longer_than_a_reader_will_take_without_a_picture():
    long_runs = []
    # A run is the prose between two figures, tables, code blocks or headings, inside a concept.
    for cid, block in concept_blocks().items():
        for run in re.split(
            r"<figure\b[\s\S]*?</figure>|<pre\b[\s\S]*?</pre>|<table\b[\s\S]*?</table>|<h[1-4]\b[\s\S]*?</h[1-4]>",
            block,
        ):
            n = len(_words(_text(run)))
            if n > MAX_PROSE_RUN:
                long_runs.append((cid, n))
    assert long_runs == [], (
        f"prose over {MAX_PROSE_RUN} words with no figure, table or code in it: {long_runs}"
    )


# The story is one chain of problems, in words a reader does not have to decode -------------------

STOPWORDS = set(
    "this that with from what when which does have must will your then they them into each only than "
    "about there their would could should still being were been".split()
)
MIN_SHARED = 2
MAX_SENTENCE_WORDS = 22
MIN_FLESCH = 55


def _content(text: str) -> set[str]:
    return {w for w in _words(text) if len(w) >= 4 and w not in STOPWORDS}


def _story(block: str) -> str:
    """What a reader reads as sentences: the hook, the body paragraphs and the bridge."""
    parts = re.findall(r'<p class="(?:hook|next)">(.*?)</p>|<div class="body">([\s\S]*?)</div>', block)
    return " ".join(_text(a or b) for a, b in parts)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]


def _syllables(word: str) -> int:
    n = len(re.findall(r"[aeiouy]+", word))
    return max(n - 1 if word.endswith("e") and n > 1 else n, 1)


def _flesch(text: str) -> float:
    ws, sents = _words(text), _sentences(text)
    return 206.835 - 1.015 * len(ws) / len(sents) - 84.6 * sum(map(_syllables, ws)) / len(ws)


def test_every_concept_ends_by_naming_the_problem_the_next_one_solves():
    # The bridge is what turns thirty essays into one chain: each answer leaves a cost, and the
    # cost is the next heading. It has to share words with that heading or it is not a bridge.
    blocks = list(concept_blocks().items())
    broken = []
    for (cid, block), (nid, following) in zip(blocks, blocks[1:], strict=False):
        bridge = re.search(r'<p class="next">(.*?)</p>', block)
        heading = _text(re.search(r"<h3>(.*?)</h3>", following).group(1))
        if not bridge:
            broken.append(f"{cid}: no bridge to {nid}")
        elif len(_content(_text(bridge.group(1))) & _content(heading)) < MIN_SHARED:
            broken.append(f"{cid}: its bridge does not lead to {nid}")
    assert broken == [], broken
    assert 'class="next"' not in blocks[-1][1], "the last concept has nothing to hand over to"


def test_the_prose_is_short_sentences_in_plain_words():
    hard = {}
    for cid, block in concept_blocks().items():
        text = _story(block)
        longest = max(len(_words(s)) for s in _sentences(text))
        score = _flesch(text)
        if longest > MAX_SENTENCE_WORDS or score < MIN_FLESCH:
            hard[cid] = f"longest sentence {longest} words, reading ease {score:.0f}"
    assert hard == {}, (
        f"prose a reader has to decode (max {MAX_SENTENCE_WORDS} words, ease {MIN_FLESCH}+): {hard}"
    )


def test_the_bridge_and_readability_gates_bite():
    assert len(_content("Which ideas are published?") & _content("Where are ideas published")) == 2
    assert _flesch("The cat sat on the mat. It was warm.") > MIN_FLESCH
    assert (
        _flesch("Notwithstanding organisational heterogeneity, instrumentation necessitates standardisation.")
        < MIN_FLESCH
    )
