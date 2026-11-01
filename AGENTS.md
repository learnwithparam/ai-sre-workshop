# AI SRE Workshop

Lab for the learnwithparam AI SRE workshop. It runs live in front of a room, so `make e2e` proves every
change before it is called done.

- `make up` starts the stack. `make down` stops it.
- `make check` runs lint, prose, unit and structural tests. It needs no Docker and no model, and CI runs it.
- `make e2e` uses the real stack, model and browser, and takes about 15 minutes.
- `make score` exits 1 below 100.

## Rules

- The e2e stamp covers what a run loads: `scripts/tree_hash.py` lists both sides with a reason each, and
  `tests/test_gate.py` fails on a path in neither.
- The score is done: each point in `scripts/rubric.py` binds one test. Add test and rubric line together.
- The SQL attendees write is the SQL the agent runs: tools load named blocks from `workshop/`, never inline.
- Every MCP tool is classified in `sre-control/sre_control/policy.py`; only `execute_remediation` acts, and
  only after a human approval event.
- The audit log is append-only; state derives from `sre.incident_events`.
- One teaching document, `docs/walkthrough.md`: six fixed sections, drawn in mermaid, every concept an anchor
  (`tests/test_walkthrough_shape.py`); `make check` parses each diagram (`scripts/check-mermaid.mjs`).
- No em dashes (`scripts/check_prose.py`). Secrets never go on a command line.
