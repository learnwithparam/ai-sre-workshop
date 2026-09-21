# AI SRE Workshop

This repository is the lab for the AI SRE workshop at learnwithparam. It runs a small, fully
instrumented web app next to ClickStack, and an AI SRE that watches it. When something breaks, a
detector opens an incident, an agent investigates it with ClickStack tools, and it proposes one
change. Nothing runs until a human approves that change, and every step lands in an audit log you
can query.

The loop described below is exercised end to end by `make e2e`, with a real model and a real
browser.

## The lab runs as one Docker Compose stack

| Service | What it is | Port |
|---|---|---|
| `clickstack` | ClickStack all-in-one: ClickHouse, the HyperDX UI, and an OpenTelemetry collector | 8080 (UI), 4317 and 4318 (OTLP) |
| `subscription-app` | A Flask signup page, instrumented with OpenTelemetry and the HyperDX browser SDK. Its footer shows the running release, so a rollback is visible on the page. Ships as two images, `v1` and a faulty `v2` | 8000 |
| `postgres-db` | Postgres, holding the `users` table the signup form writes to | internal |
| `docs-loader` | A Go service behind the app's `/load-docs` route, with a handler that never returns | internal |
| `traffic` | Steady page views and signups, so every signal has a baseline | none |
| `sre-control` | The control plane behind the AI SRE Control pages: detector, incidents and approvals, the SRE MCP server, the remediation runner | 8090 |
| `mcp-clickhouse` | ClickHouse's official MCP server, for read-only SQL | internal |
| `librechat` and `mongodb` | The AI SRE workspace, on OpenRouter's `deepseek-v4-flash`, connected to both MCP servers | 3080 |
| `otel-collector` and `socat` | Container CPU and memory stats from the Docker socket | none |
| `load-generator` | Optional browser traffic (Locust and Chromium, 1.3 GB), under the `browser-load` profile | none |

The browser, Flask, Go, LibreChat, both MCP servers and sre-control all report to ClickStack, so
you can follow one trace from a click on the page to the database write, and you can watch the AI
SRE's own model calls and tool calls in the same place.

## Your machine needs Docker with about 8 GB of memory

The stack uses about 3.2 GB: `clickstack` about 1.8 GB, `librechat` and `mongodb` about 0.8 GB, and
every other service under 150 MB. We run it on an Apple M1 with 16 GB of RAM and Docker Desktop
limited to 8 GB. The e2e suite adds a headless Chromium on the host.

## Start the lab

1. Start ClickStack, open http://localhost:8080, create your HyperDX account, and copy the
   ingestion API key from Team Settings.
   ```bash
   docker compose -f docker-compose.all-in-one.yml up -d clickstack
   ```
2. Put two keys in `.env` at the repo root (the file is git-ignored):
   ```bash
   HYPERDX_API_KEY=<your ingestion key>
   OPENROUTER_API_KEY=<your OpenRouter key>
   ```
3. Generate every other secret, build both app releases, start everything, and create the workshop
   logins:
   ```bash
   make env
   make up
   ```
4. Open the pages. Logins are in `.env`.

| Page | URL | Login |
|---|---|---|
| Signup app | http://localhost:8000 | none |
| HyperDX | http://localhost:8080 | your account, or `HYPERDX_USER_EMAIL` |
| AI SRE Control | http://localhost:8090 | `SRE_APPROVER_EMAIL` |
| LibreChat | http://localhost:3080 | `LIBRECHAT_USER_EMAIL` |

Stop it with `make down`. Your data stays in `./clickstack/`, `./postgresql-db/` and the
`librechat_mongodb` volume.

## Run the AI SRE loop

```bash
make chaos SCENARIO=bad-release
```

1. The detector compares the last minute of errors with a 3 sigma bound over a baseline that
   leaves out past incidents, and with a fixed 10% SLO ceiling for when there is no clean baseline
   yet. It opens an incident within about a minute, on http://localhost:8090.
2. **Investigate with AI SRE** opens LibreChat with the incident. The agent calls the SRE tools
   (anomalies, time series, event deltas, a trace waterfall), names the release that broke, and
   calls `propose_remediation` with trace ids as evidence.
3. The proposal is refused if any trace id, service or release it cites has no telemetry, and if
   the action is outside policy. A stored proposal waits as `pending`.
4. Ask the agent to execute it anyway. `execute_remediation` is refused and the refusal is recorded.
   The guardrail is the server, not the prompt.
5. Open the approval link, read the evidence and the blast radius, and click **Approve**. Tell the
   agent. It executes the rollback, and sre-control verifies recovery on a minute of fresh traffic
   before it resolves the incident.

The second scenario, `make chaos SCENARIO=docs-hang`, hangs requests inside docs-loader. Try
**Reject**, then **Edit** the action to `restart_service docs-loader`, then **Approve**.
`make chaos-reset` puts both back.

## What the AI SRE may do

| Tool | Class | Server |
|---|---|---|
| `list_sources`, `service_timeseries`, `analyze_service_anomalies`, `get_event_deltas`, `event_patterns`, `get_trace_waterfall`, `search_logs`, `list_incidents`, `get_incident`, `get_remediation_status` | read | sre-control |
| `run_query`, `list_databases`, `list_tables` | read, as the ClickHouse user `sre_agent` | mcp-clickhouse |
| `propose_remediation` | stores a pending proposal | sre-control |
| `execute_remediation` | runs `rollback_release` or `restart_service`, only after a human approval | sre-control |

`sre_agent` is read-only in ClickHouse itself (`readonly=2`, a 10 second limit, a 1 GB memory
limit, 10,000 result rows), so even raw SQL from the model cannot write or starve ingest. The
policy lives in `sre-control/sre_control/policy.py`, and a structural test fails if a tool is not
classified.

To roll back a release, sre-control runs `docker compose up` for the previous image through the
host's Docker socket, the same command an operator would type. It builds that command from a fixed
list of two actions and never from text the model wrote.

## The workshop SQL is the agent's SQL

`workshop/` holds the queries attendees write, as named blocks. sre-control loads the same blocks
for its tools, so a query improved in the workshop improves the agent.

| File | Module |
|---|---|
| `workshop/01-substrate.sql` | 1: tables, services, latency percentiles |
| `workshop/02-anomaly.sql` | 2: time series, 3 sigma, the anomaly materialized view |
| `workshop/03-event-deltas.sql` | 3: event deltas, log patterns, stuck requests |
| `workshop/04-trace-graph.sql` | 3 and 4: trace waterfall, errors by release, grounding checks |

## Gates

| Command | What it proves |
|---|---|
| `make check` | Lint, unit and structural tests, compose validity for every mode, prose rules. No Docker, no model spend. CI runs it on every push. |
| `make e2e` | The full stack with the real model and a real browser: telemetry, workshop SQL, the signup page at phone width, the HyperDX views the workshop teaches from, detection, investigation, refusal, approval, rollback, verification, reject and edit, self-observability, MCP auth. About 13 minutes after the stack is up; writes `evidence/e2e-report.json` and the screenshots `guide.html` shows. |
| `make book` | Redraws every figure, renders the attendee workbook and the facilitator guide to PDF, then reads them back with `pdftotext`. A Chromium PDF can look perfect and extract as gibberish, so the build asserts every canary phrase and every command line survives, that no run is welded or split one letter at a time, that both fonts are embedded and that no page is mostly empty. Needs poppler. |
| `make score` | A score out of 100, computed from the latest `check` and `e2e` results. Results from older code count as missing. Below 100 exits 1. |

`workbook.html` explains every idea the workshop rests on, and `guide.html` is the facilitator guide
for running the day. The guide cites the concepts by name rather than repeating them, and a
structural test fails on a dangling citation, on an explanation no module delivers, and on any
sentence written into both. `make book` prints all of it.

## Run it on a VPS

`docker-compose.vps.yml` puts Caddy in front with TLS and publishes only ports 80 and 443. Point
five DNS names at the server (`app`, `otlp`, `hyperdx`, `chat` and `sre`, each under your domain),
set `PUBLIC_DOMAIN` in `.env`, and run:

```bash
make env
make up-vps
```

Registration is off in LibreChat, sre-control requires the approver login, and HyperDX uses its
own accounts. `make check` verifies this layer structurally: the override is valid, only Caddy
publishes ports, and the e2e suite builds its browser URLs from `PUBLIC_DOMAIN`. It has not yet been
run against a live server.

## Where this came from

The lab started from ClickHouse's
[clickstack-demo-subscription-app](https://github.com/ClickHouse/clickstack-demo-subscription-app),
released under the Apache 2.0 license in `LICENSE`, kept as the `upstream` git remote. The agent
workspace follows ClickHouse's [agentic-data-stack](https://github.com/ClickHouse/agentic-data-stack),
and the tool set follows [ClickStack's AI SRE tools](https://clickhouse.com/clickstack/ai-sre-observability).
