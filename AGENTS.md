# AI SRE Workshop

Lab for the learnwithparam AI SRE workshop. It runs live in front of a room, so `make e2e` proves every
change before it is called done.

- `make up` starts the stack. `make down` stops it.
- `make check` runs lint, prose, unit and structural tests. It needs no Docker and no model, and CI runs it.
- `make book` prints both PDFs.
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
- Two documents, two PDFs: `workbook.html` holds each idea once; `guide.html` cites them by id (`tests/test_concepts.py`).
- Every figure is drawn by `scripts/diagram.mjs` from `design/diagrams/<id>.json` (`make diagrams`); a concept with no
  figure needs a reason in `design/diagrams/exempt.json` (`tests/test_diagrams.py`). Colours and type live in `design/BRAND.md`.
- `make book` records source hashes and `make check` names a stale PDF. Never judge a PDF by eye: resets
  live in `design/book.css` (`tests/test_book.py`) and `make book` reads back with `pdftotext`.
- Code blocks, tables and figures keep 5 mm before what follows: `make book` measures it and fails below.
- `.githooks/pre-commit` runs `make book` when a commit stages a PDF source, then stages the PDFs. Arm it once
  per clone: `git config core.hooksPath .githooks`.
- Titles are claims that name the subject, in sentence case; `python3 ~/.claude/skills/lwp-shared/scripts/house_rules.py --voice --terms` on `workbook.html` and `guide.html` must report 0.
- No em dashes (`scripts/check_prose.py`). Secrets never go on a command line.
