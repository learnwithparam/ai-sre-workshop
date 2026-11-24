# AI SRE Workshop

Lab for the learnwithparam AI SRE workshop. A learner works through it alone from `docs/learner/`, and it
also runs live. `make e2e` proves every change before it is called done.

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
- Learners follow `docs/learner/`, one lesson per exercise plus setup and the live incident: each opens with
  why, has a mermaid picture, and an `Expect:` line after every bash block. `docs/walkthrough.md` holds the
  ideas: six fixed sections, every concept an anchor. `tests/test_walkthrough_shape.py` checks both, and
  `make check` parses each diagram (`scripts/check-mermaid.mjs`).
- Lessons and README read at grade 6 or below (`scripts/learner-clarity.mjs`). It and `scripts/plain-english.mjs`
  are copies from the private teach repo, which checks they match: edit them there, never here.
- Facilitator notes live in the teach repo, never in this public repo.
- No em dashes (`scripts/check_prose.py`). Secrets never go on a command line.
