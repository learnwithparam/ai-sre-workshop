"""Every tool query lives in the workshop SQL attendees write, and every one is bounded."""

import re
from pathlib import Path

from sre_control.queries import TOOL_QUERIES, load_queries

WORKSHOP = Path(__file__).resolve().parents[2] / "workshop"


def test_every_tool_query_exists_in_the_workshop_sql():
    queries = load_queries(WORKSHOP)
    assert set(TOOL_QUERIES.values()) <= set(queries)


def test_every_query_reads_and_is_bounded():
    for name, query in load_queries(WORKSHOP).items():
        first = query.sql.lstrip().split(None, 1)[0].upper()
        assert first in ("SELECT", "WITH", "CREATE"), name
        if first != "CREATE":
            assert re.search(r"\bLIMIT\s+\{?\w", query.sql, re.I), f"{name} has no LIMIT"


def test_parameters_are_bound_never_formatted():
    for name, query in load_queries(WORKSHOP).items():
        assert "{" not in query.sql or re.search(r"\{\w+:\w", query.sql), name
        assert "%s" not in query.sql and "format(" not in query.sql.lower(), name


def test_example_values_may_contain_spaces():
    example = load_queries(WORKSHOP)["search_logs"].example
    assert example == {
        "service": "subscription-backend",
        "text": "POST /api/subscribe",
        "minutes": "60",
    }
