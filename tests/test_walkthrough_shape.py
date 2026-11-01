"""docs/walkthrough.md is the one teaching document: fixed sections, diagrams, anchored concepts."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "walkthrough.md"
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


def test_every_module_exercise_states_what_to_expect():
    text = DOC.read_text()
    modules = re.findall(r"^### Module \d.*$", text, re.M)
    assert len(modules) == 5
    assert text.count("Expect:") >= 5


def test_readme_links_the_walkthrough():
    assert "docs/walkthrough.md" in (ROOT / "README.md").read_text()
