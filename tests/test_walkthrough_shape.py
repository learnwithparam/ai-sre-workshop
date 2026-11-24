"""docs/walkthrough.md holds the ideas: fixed sections, diagrams, anchored concepts. docs/learner/ holds the
lessons a learner follows alone, in the buildcamp lesson shape: why with reading, a drawing of the system,
steps that each say how to verify, and every evidence screen placed on some lesson."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "walkthrough.md"
LESSONS = ROOT / "docs" / "learner"
LESSON_SECTIONS = (
    "Goal",
    "Before",
    "Starting point",
    "Use it",
    "How to verify you are done",
    "Wrap-up",
    "If you get stuck",
    "Next",
)
DIAGRAM = re.compile(r"!\[[^\]]+\]\(\.\./images/diagrams/([\w-]+\.svg)\)")
SECTIONS = [
    "The problem",
    "What you build",
    "How it works",
    "Run it",
    "What to watch for",
    "Where to go next",
]
CONCEPTS = """action-list approval-event approval-fatigue audit-log autonomy-level baseline burn-rate
cardinality context-poisoning error-budget eval-set event-delta excessive-agency grounding
guardrail-source incident-exclusion least-privilege log-pattern loop prompt-injection recovery-check
risk-source sampling signals sli slo symptom-alerting three-sigma tool-class trace-graph wide-event""".split()


def test_walkthrough_has_the_six_sections_in_order():
    assert re.findall(r"^## (.+)$", DOC.read_text(), re.M)[: len(SECTIONS)] == SECTIONS


def test_walkthrough_draws_at_least_two_diagrams():
    assert DOC.read_text().count("```mermaid") >= 2


def test_every_concept_has_an_anchor():
    text = DOC.read_text()
    missing = [c for c in CONCEPTS if f'<a id="c-{c}"></a>' not in text]
    assert missing == []


def test_every_exercise_has_a_lesson_with_expect():
    exercises = sorted((ROOT / "workshop" / "exercises").glob("*.sql"))
    assert len(exercises) == 5
    for exercise in exercises:
        name = re.search(r"^-- name: (\w+)", exercise.read_text(), re.M).group(1)
        lesson = (LESSONS / exercise.name.replace(".sql", ".md")).read_text()
        assert f"make exercise N={int(exercise.name[:2])}" in lesson, exercise.name
        assert f"Expect: `match: {name} returns the same N row(s) as the solution`" in lesson, exercise.name


def test_every_lesson_has_its_shape():
    lessons = sorted(LESSONS.glob("*.md"))
    assert [p.name[:2] for p in lessons] == [f"{n:02d}" for n in range(len(lessons))]
    for lesson in lessons:
        text = lesson.read_text()
        headings = re.findall(r"^## (.+)$", text, re.M)
        assert headings[0].startswith("Why"), lesson.name
        missing = [h for h in LESSON_SECTIONS if h not in headings]
        assert missing == [], f"{lesson.name}: {missing}"
        assert text.startswith(f"# {lesson.name[:2]} "), f"{lesson.name}: the title starts with its number"
        assert "Complementary materials:" in text, f"{lesson.name}: the why needs reading links"
        steps = re.split(r"^## ", text, flags=re.M)
        step_bodies = [b for b in steps if b.startswith("Step ")]
        assert step_bodies, f"{lesson.name}: no Step headings"
        for body in step_bodies:
            assert "**Verify:**" in body, f"{lesson.name}: {body.splitlines()[0]} has no Verify line"
        for image in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", text):
            assert (lesson.parent / image).resolve().is_file(), f"{lesson.name}: {image}"
        for block in re.finditer(r"```bash\n.*?```\n\n([^\n]*)", text, re.S):
            assert block.group(1).startswith("Expect:"), f"{lesson.name}: a bash block lacks an Expect: line"


def test_every_lesson_draws_its_system():
    """Each lesson shows a canvas drawing that exists, and no two lessons share one."""
    drawings = []
    for lesson in sorted(LESSONS.glob("*.md")):
        found = DIAGRAM.findall(lesson.read_text())
        assert found, f"{lesson.name}: no drawing from docs/images/diagrams/"
        assert all((ROOT / "docs" / "images" / "diagrams" / name).is_file() for name in found), lesson.name
        drawings += found
    assert len(drawings) == len(set(drawings))
    on_disk = {p.name for p in (ROOT / "docs" / "images" / "diagrams").glob("*.svg")}
    assert on_disk == set(drawings), f"unused drawings: {on_disk - set(drawings)}"


def test_every_evidence_screen_is_on_a_lesson():
    text = "".join(p.read_text() for p in LESSONS.glob("*.md"))
    screens = sorted((ROOT / "evidence" / "screens").glob("*.png"))
    assert screens
    unused = [p.name for p in screens if f"evidence/screens/{p.name}" not in text]
    assert unused == []


def test_walkthrough_links_every_lesson():
    text = DOC.read_text()
    missing = [p.name for p in sorted(LESSONS.glob("*.md")) if f"learner/{p.name}" not in text]
    assert missing == []


def test_readme_links_the_walkthrough():
    readme = (ROOT / "README.md").read_text()
    assert "docs/walkthrough.md" in readme
    assert all(f"docs/learner/{p.name}" in readme for p in LESSONS.glob("*.md"))
