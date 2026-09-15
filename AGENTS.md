# AI SRE Workshop

Lab for the learnwithparam AI SRE workshop. **This is teaching material that has to work live in
front of a room.** A step that fails on stage costs the session, so every change is proven by
`make e2e` before it is called done.

## Running it

```bash
make up      # stack, both app releases, workshop logins
make check   # lint, unit and structural tests, no Docker, no model spend (CI runs this)
make e2e     # real stack, real model, real browser; about 15 minutes
make score   # 0 to 100 from the latest check and e2e results; below 100 exits 1
make down
```

## Rules

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
- **No em dashes** in prose; `scripts/check_prose.py` enforces it for `teach.html`, `README.md`
  and this file.
