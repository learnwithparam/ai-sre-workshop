"""Every exercise is a workshop block with a blank, and its solution is the block the agent runs."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sre-control"))
from sre_control.queries import BLOCK, load_queries  # noqa: E402

WORKSHOP = ROOT / "workshop"
EXERCISES = sorted((WORKSHOP / "exercises").glob("*.sql"))


def body_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("--")]


def test_there_is_an_exercise_for_each_module():
    assert [p.name[:2] for p in EXERCISES] == ["01", "02", "03", "04", "05"]


def test_every_exercise_has_a_solution_block_and_a_blank():
    solutions = load_queries(WORKSHOP)
    for path in EXERCISES:
        ((name, body),) = BLOCK.findall(path.read_text())
        assert name in solutions, f"{path.name}: no solution block {name}"
        assert len(re.findall(r"\bTODO\b", body)) == 1, f"{path.name} needs exactly one TODO"
        assert "-- example:" in body, f"{path.name} lacks the example line"
        solution_file = next(WORKSHOP.glob(f"{path.name[:2]}-*.sql"))
        solution_lines = set(body_lines(dict(BLOCK.findall(solution_file.read_text()))[name]))
        other = [line for line in body_lines(body) if "TODO" not in line and line not in solution_lines]
        assert other == [], f"{path.name} differs from its solution beyond the blank: {other}"


def test_exercises_are_not_loaded_as_agent_queries():
    assert not any(p.parent.name == "exercises" for p in WORKSHOP.glob("*.sql"))


def test_exercise_target_is_wired():
    makefile = (ROOT / "Makefile").read_text()
    assert re.search(r"^exercise:.*\n\t.*scripts/exercise\.py \$\(N\)", makefile, re.M)
