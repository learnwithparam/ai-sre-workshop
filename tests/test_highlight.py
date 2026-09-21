"""Every code block in the workbook and the guide is coloured by scripts/highlight.mjs.

A block is plain text the tool colours, so a hand edit is overwritten and named. The colours are
token classes: each has a style bound to a palette variable, and the palette pairs are already
pinned by tests/test_house.py.
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["workbook.html", "guide.html"]
CSS = (ROOT / "design/book.css").read_text()
CLASSES = ["hl-k", "hl-s", "hl-n", "hl-c"]


def node(code: str) -> str:
    """Run a snippet against the tool's exports and return what it prints."""
    run = subprocess.run(
        ["node", "--input-type=module", "-e", f'import * as h from "./scripts/highlight.mjs"; {code}'],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    return run.stdout


def test_every_block_is_what_the_tool_writes():
    run = subprocess.run(
        ["node", "scripts/highlight.mjs", "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr


def test_every_pre_names_its_language():
    for name in PAGES:
        text = (ROOT / name).read_text()
        assert re.findall(r"<pre(?![^>]*data-lang=)[^>]*>", text) == [], (
            f"{name} has a <pre> with no data-lang"
        )


def test_every_language_a_page_uses_is_one_the_tool_knows():
    known = set(json.loads(node("console.log(JSON.stringify(h.LANGS))")))
    used = {m for name in PAGES for m in re.findall(r'<pre data-lang="([a-z]+)"', (ROOT / name).read_text())}
    assert used <= known, f"unknown code languages: {sorted(used - known)}"


def test_sql_gets_a_keyword_a_string_a_number_and_a_comment():
    src = "SELECT service, count() -- one row\nFROM t WHERE severity = 'ERROR' AND n > 30"
    out = node(f"console.log(h.highlight('sql', {json.dumps(src)}))")
    for cls in CLASSES:
        assert f'class="{cls}"' in out, f"{cls} never appears"


def test_colouring_never_changes_the_text():
    src = "docker exec -it x --param_a=1 # note\nmake up\n"
    out = node(f"console.log(JSON.stringify(h.plainText(h.highlight('bash', {json.dumps(src)}))))")
    assert json.loads(out) == src


def test_a_hand_edit_inside_a_block_is_named():
    page = '<pre data-lang="sql">SELECT <span class="hl-s">1</span></pre>'
    off = json.loads(node(f"console.log(JSON.stringify(h.stale({json.dumps(page)})))"))
    assert off == ["SELECT 1"]


def test_every_colour_class_has_a_style_bound_to_a_palette_variable():
    for cls in CLASSES:
        assert re.search(rf"\.{cls}\s*\{{[^}}]*var\(--c-", CSS), (
            f"{cls} has no token-bound style in design/book.css"
        )


def test_xml_gets_tags_strings_and_numbers():
    out = node("console.log(h.highlight('xml', '<readonly>2</readonly> <x a=\"b\"/>'))")
    for cls in ["hl-k", "hl-s", "hl-n"]:
        assert f'class="{cls}"' in out, f"{cls} never appears"


# Code in the workbook is the lab's code -----------------------------------------------------------

COPY = re.compile(r'<pre data-lang="[a-z]+" data-from="([^"]+)">([\s\S]*?)</pre>')


def _plain(inner: str) -> str:
    import html

    return html.unescape(re.sub(r"<[^>]+>", "", inner)).strip("\n")


def _named_sql(path: Path, name: str) -> str:
    text = path.read_text()
    m = re.search(rf"-- name: {re.escape(name)}\n(?:--[^\n]*\n)*([\s\S]*?;)\n", text)
    assert m, f"{path.name} has no block named {name}"
    return m.group(1)


def _contains_lines(source: str, excerpt: str) -> bool:
    """The excerpt's lines, indent aside, appear one after another in the source."""
    have = [ln.strip() for ln in source.splitlines()]
    want = [ln.strip() for ln in excerpt.splitlines() if ln.strip()]
    have = [ln for ln in have if ln]
    return any(have[i : i + len(want)] == want for i in range(len(have) - len(want) + 1))


def test_a_workbook_code_block_is_a_copy_of_the_lab_file_it_names():
    blocks = COPY.findall((ROOT / "workbook.html").read_text())
    assert blocks, "the workbook shows no code copied from the lab"
    off = []
    for ref, inner in blocks:
        path, _, name = ref.partition("#")
        file = ROOT / path
        assert file.exists(), f"data-from names {path}, which does not exist"
        shown = _plain(inner)
        ok = (
            shown.strip() == _named_sql(file, name).strip()
            if name
            else _contains_lines(file.read_text(), shown)
        )
        if not ok:
            off.append(ref)
    assert off == [], f"code blocks that no longer match the lab file they were copied from: {off}"


def test_every_code_block_in_the_workbook_says_which_lab_file_it_is_copied_from():
    # A block with no data-from is code nobody can check. It once shipped as a bare file path.
    page = (ROOT / "workbook.html").read_text()
    loose = [m.group(1)[:40] for m in re.finditer(r'<pre data-lang="\w+">([\s\S]*?)</pre>', page)]
    assert loose == [], f"workbook code blocks with no data-from: {loose}"
