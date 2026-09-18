# AI SRE Workshop

Lab for the learnwithparam AI SRE workshop. **This is teaching material that has to work live in
front of a room.** A step that fails on stage costs the session, so every change is proven by
`make e2e` before it is called done.

## Running it

```bash
make up      # stack, both app releases, workshop logins
make check   # lint, prose, unit and structural tests, no Docker, no model spend (CI runs this)
make book    # render the bound PDF, the concepts and the run sheet, then read the text layer back
make e2e     # real stack, real model, real browser; about 15 minutes
make score   # 0 to 100 from the latest check and e2e results; below 100 exits 1
make down
```

## Rules

- **The end-to-end stamp covers what a run loads, and nothing else.** `scripts/tree_hash.py`
  carries two lists with a reason per entry, the Makefile is stamped recipe by recipe, and
  `tests/test_gate.py` fails when a tracked path is claimed by neither. Adding a target that cannot
  reach the stack must not cost a fifteen-minute rerun; a change to a workshop query must.
- **The score is the definition of done.** Every point in `scripts/rubric.py` is bound to one test,
  and `tests/test_gate.py` fails if the rubric names a test that does not exist. Add the test and
  the rubric line in the same change.
- **The SQL attendees write is the SQL the agent runs.** Tools load named blocks from `workshop/`.
  Change a query there, never inline in Python.
- **Every MCP tool is classified** in `sre-control/sre_control/policy.py`. Only
  `execute_remediation` can act, and only after a human approval event. A new tool that is not
  classified cannot register.
- **The audit log is append-only.** State is derived from `sre.incident_events`; never update rows.
- **Secrets never go on a command line.** Pass them through the environment or stdin, as
  `e2e/lib/stack.ts` and `scripts/bootstrap_users.py` do.
- **No em dashes** in prose; `scripts/check_prose.py` enforces it across every tracked markdown and
  HTML file. It took a list of three named files until a fourth surface was written and checked by
  nothing.
- **The teach surfaces hold one copy of each idea.** Explanations live in `concepts.html`.
  `teach.html` carries the timing, the talk track and the commands, and cites concepts by id.
  `tests/test_concepts.py` fails on a dangling citation, on an explanation no module delivers, and
  on any phrase written twice.
- **A page that changed and a PDF that did not is a stale book.** `make book` rebuilds every PDF and
  records the hash of each source it read, the builder included. `make check` fails and names the
  file when one has moved since.
- **Never judge a generated PDF by looking at it.** Six CSS properties render perfectly and destroy
  the text layer. They are reset in the print block of `teach.css`, `tests/test_book.py` asserts the
  resets are still there, and `make book` reads its own output with `pdftotext`.
