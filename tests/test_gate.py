"""Phase 1: the gate itself is wired, and the scorecard cannot drift from the tests it scores."""

import ast
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from rubric import PHASES  # noqa: E402

REQUIRED_TARGETS = {"check", "e2e", "score", "chaos", "chaos-reset", "up", "down"}


def make_targets() -> set[str]:
    text = (ROOT / "Makefile").read_text()
    return set(re.findall(r"^([a-z][a-z0-9-]*):", text, flags=re.M))


def test_make_targets_exist():
    assert REQUIRED_TARGETS <= make_targets()


def test_ci_runs_make_check():
    workflow = yaml.safe_load((ROOT / ".github/workflows/check.yml").read_text())
    runs = [step.get("run", "") for job in workflow["jobs"].values() for step in job["steps"]]
    assert any(re.search(r"\bmake check\b", run) for run in runs)
    triggers = workflow.get("on", workflow.get(True))
    assert "push" in triggers and "pull_request" in triggers


def pytest_ids() -> set[str]:
    ids = set()
    for path in list(ROOT.glob("tests/test_*.py")) + list(ROOT.glob("sre-control/tests/test_*.py")):
        tree = ast.parse(path.read_text())
        rel = path.relative_to(ROOT).as_posix()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
                ids.add(f"{rel}::{node.name}")
    return ids


def playwright_ids() -> set[str]:
    ids = set()
    for path in (ROOT / "e2e/specs").glob("*.spec.ts"):
        for title in re.findall(r"""\btest\(\s*(["'`])(.+?)\1""", path.read_text()):
            ids.add(f"{path.name} > {title[1]}")
    return ids


def test_every_scored_check_exists():
    known = {"junit": pytest_ids(), "pw": playwright_ids()}
    checks = [c for checks in PHASES.values() for c in checks]
    missing = [c.id for c in checks if c.id not in known[c.source]]
    assert missing == []
    assert sum(c.points for c in checks) == 100
    assert len({c.id for c in checks}) == len(checks)


def test_prose_check_is_wired():
    teach_test = (ROOT / "tests/test_teach.py").read_text()
    assert "check_prose" in teach_test
    assert (ROOT / "scripts/check_prose.py").exists()

    # The word lists are a committed copy of the house rules. Where the rules exist it must match them.
    from check_prose import PHRASES, WORDS, rules_stale

    assert WORDS and PHRASES, "scripts/prose-rules.json has no rules, so the check would pass everything"
    assert rules_stale() is None


def test_e2e_cleanup_trap_survives_the_cd():
    # The trap fires after `cd e2e`; a relative script path left v2 deployed after a failed run.
    trap = next(line for line in (ROOT / "Makefile").read_text().splitlines() if "trap " in line)
    assert "$(CURDIR)/scripts/chaos.py reset" in trap


def test_every_tracked_path_is_on_one_side_of_the_stamp():
    """A new directory cannot quietly end up uncovered by the end-to-end stamp.

    The stamp used to be "everything except a list of prose", so a file nobody thought
    about was stamped by default: a new teaching page silently invalidated every
    recorded run, and an unrelated Makefile target cost a fifteen-minute rerun. Now
    nothing is on either side by default, and this is what makes somebody choose.
    """
    from tree_hash import tracked, unclassified

    orphans = unclassified(tracked(include_prose=True))
    assert orphans == [], (
        f"{len(orphans)} path(s) claimed by neither STAMPED nor NOT_STAMPED in "
        f"scripts/tree_hash.py, first: {orphans[:3]}. Say which side they are on, with the reason."
    )


def test_the_stamp_covers_what_an_e2e_run_loads():
    """And not what it cannot reach."""
    from tree_hash import is_stamped

    assert is_stamped("sre-control/sre_control/detector.py"), "the control plane under test is not stamped"
    assert is_stamped("workshop/02-anomaly.sql"), "a query the agent's tools load is not stamped"
    assert is_stamped("e2e/specs/07-bad-release.spec.ts"), "a spec is not stamped"
    assert not is_stamped("design/book.css"), "a print stylesheet cannot change what a run proved"
    assert not is_stamped("tests/test_book.py"), "a unit test is not loaded by a spec"
    assert not is_stamped("scripts/build_book.mjs"), "the PDF builder is not loaded by a spec"


def test_the_makefile_is_stamped_by_recipe_and_the_recipes_exist():
    """The one file with mixed concerns: it runs the stack and it prints a PDF.

    If a rename made the extraction return nothing, the stamp would still look healthy
    while covering less than it claims, so a missing recipe raises rather than skips.
    """
    from tree_hash import E2E_RECIPES, makefile_slice

    slice_ = makefile_slice()
    for target in E2E_RECIPES:
        assert f"{target}:" in slice_, f"the {target} recipe is missing from the stamped slice"
    assert "npx playwright test" in slice_, "the slice does not contain the command that runs the specs"
    assert "book:" not in slice_, "a target that cannot touch the stack is inside the stamp"
