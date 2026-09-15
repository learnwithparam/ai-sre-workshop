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
