# AI SRE Workshop

Lab for the learnwithparam AI SRE workshop. It runs live in front of a room, so `make e2e` proves every
change before it is called done.

`make up` · `make check` (lint, prose, unit, structural; no Docker, no model; CI runs it) · `make book` ·
`make e2e` (real stack, model and browser, about 15 minutes) · `make score` (below 100 exits 1) · `make down`.

## Rules

- The e2e stamp covers what a run loads: `scripts/tree_hash.py` lists both sides with a reason each, and
  `tests/test_gate.py` fails on a path in neither.
- The score is done: each point in `scripts/rubric.py` binds one test. Add test and rubric line together.
- The SQL attendees write is the SQL the agent runs: tools load named blocks from `workshop/`, never inline.
- Every MCP tool is classified in `sre-control/sre_control/policy.py`; only `execute_remediation` acts, and
  only after a human approval event.
- The audit log is append-only; state derives from `sre.incident_events`.
- `concepts.html` holds each idea once; `teach.html` cites them by id (`tests/test_concepts.py`).
- `make book` records source hashes and `make check` names a stale PDF. Never judge a PDF by eye: resets
  live in `teach.css` (`tests/test_book.py`) and `make book` reads back with `pdftotext`.
- No em dashes (`scripts/check_prose.py`). Secrets never go on a command line.
