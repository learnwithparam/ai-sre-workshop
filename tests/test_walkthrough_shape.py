"""docs/walkthrough.md holds the ideas: fixed sections, diagrams, anchored concepts. docs/learner/ holds the
lessons a learner follows alone: one per exercise, each with its picture, its commands and what to expect."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "walkthrough.md"
LESSONS = ROOT / "docs" / "learner"
LESSON_SECTIONS = ("Goal", "Starting point", "If you get stuck")
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
        assert all(h in headings for h in LESSON_SECTIONS), lesson.name
        assert "```mermaid" in text, lesson.name
        for image in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", text):
            assert (lesson.parent / image).resolve().is_file(), f"{lesson.name}: {image}"
        for block in re.finditer(r"```bash\n.*?```\n\n([^\n]*)", text, re.S):
            assert block.group(1).startswith("Expect:"), f"{lesson.name}: a bash block lacks an Expect: line"


def test_walkthrough_links_every_lesson():
    text = DOC.read_text()
    missing = [p.name for p in sorted(LESSONS.glob("*.md")) if f"learner/{p.name}" not in text]
    assert missing == []


def test_readme_links_the_walkthrough():
    readme = (ROOT / "README.md").read_text()
    assert "docs/walkthrough.md" in readme
    assert all(f"docs/learner/{p.name}" in readme for p in LESSONS.glob("*.md"))
