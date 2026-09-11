# AI SRE Workshop

This repository is the lab for the AI SRE workshop at learnwithparam. It runs a small, fully
instrumented web app next to an observability stack, so every page view, request, database call and
log line lands somewhere you can query. The workshop uses it to practise the core SRE loop: notice a
symptom, find the evidence, name the cause. Then we do the same work with an AI assistant and compare
the two.

We will keep adding services, failure scenarios and exercises here as the workshop grows.

## The lab runs as one Docker Compose stack

| Service | What it is | Port |
|---|---|---|
| `clickstack` | ClickStack all-in-one: ClickHouse for storage, the HyperDX UI for search, and an OpenTelemetry collector for ingest | 8080 (UI), 4317 and 4318 (OTLP) |
| `subscription-app` | A Flask app serving a signup page. The backend is instrumented with OpenTelemetry, and the page loads the HyperDX browser SDK, which records sessions, console output and network calls | 8000 |
| `postgres-db` | Postgres, holding the `users` table the signup form writes to | internal |
| `docs-loader` | A Go service called by the app's `/load-docs` route. Its logs carry the trace ID of the request that caused them | 8001 |
| `load-generator` | Locust driving headless Chromium through Playwright, so the traffic includes real browser sessions and not only HTTP requests | none |
| `otel-collector` and `socat` | A second collector that reads container CPU and memory stats from the Docker socket | none |

The browser, the Flask backend and the Go service all report to ClickStack, so you can follow one
trace from a click on the page to the database write.

## Your machine needs Docker with about 8 GB of memory

With the load generator running, `clickstack` uses about 1.8 GB and `load-generator` about 1.3 GB.
Every other service stays under 100 MB. We run the lab on an Apple M1 with 16 GB of RAM, with Docker
Desktop limited to 8 GB and 6 CPUs. Giving Docker the whole machine makes everything slower, because
macOS starts swapping.

## Start the lab in two passes

The app needs an ingestion key, and the key only exists after you create an account in HyperDX. So
ClickStack starts first.

1. Start ClickStack on its own:
   ```bash
   docker compose -f docker-compose.all-in-one.yml up -d clickstack
   ```
2. Open http://localhost:8080, create an account, and copy the ingestion API key from Team Settings.
3. Put the key in a `.env` file at the repo root. The file is git-ignored.
   ```bash
   HYPERDX_API_KEY=<your ingestion key>
   ```
4. Start everything else:
   ```bash
   docker compose -f docker-compose.all-in-one.yml up -d
   ```
5. Open the app at http://localhost:8000 and HyperDX at http://localhost:8080. Within a minute you
   should see traces from `subscription-frontend`, `subscription-backend` and `docs-loader`, and
   recorded browser sessions under Client Sessions.

## Stop the lab when you are not using it

The load generator restarts itself and runs until you stop it, so stop the stack after each session:

```bash
docker compose -f docker-compose.all-in-one.yml down
```

`down` keeps your data. The HyperDX account and the ClickHouse data live in `./clickstack/`, and the
Postgres data lives in `./postgresql-db/`. Both are git-ignored. Delete those folders to start from
nothing.

To keep the stack running but stop the traffic:

```bash
docker compose -f docker-compose.all-in-one.yml stop load-generator
```

## The app ships with faults to investigate

These defects make good exercises. Try to find each one from the telemetry before you read the code.

- **A request that never finishes.** The "load docs" link calls `/load-docs`, which calls the Go
  service's `/load` handler. That handler allocates 1 MB every 10 ms in a loop that never returns
  (`docs-loader/main.go`), and the Flask side calls it with no timeout
  (`subscription-app/flask_app.py`). The browser waits and never gets an answer, and the loop keeps
  running inside `docs-loader` after the browser gives up. What does this look like in the traces? And
  why does `docs-loader` stay well under its 10 MB memory limit while "allocating" all that memory?
- **A log line that lies.** After a signup, the backend logs `New subscription from ******** via ...`,
  but the value it prints is `insert_data[0][3]`, the fourth character of the name, not the signup
  source. Find it by comparing the log with the `source` column stored in Postgres.
- **User actions that are never recorded.** The page has `HyperDX.addUserAction` calls for a
  successful submit, a failed submit and a network error, all commented out
  (`subscription-app/templates/index.html`). Wiring them in is the first instrumentation exercise.

## Other ways to run it

- `docker-compose.yml` sends data to a ClickHouse Cloud service instead of a local ClickHouse. It needs
  `CLICKHOUSE_ENDPOINT`, `CLICKHOUSE_USER` and `CLICKHOUSE_PASSWORD` in `.env` alongside the key.
- `k8s/` holds Kubernetes manifests for the same stack. See `k8s/README.md`.

## Where this came from

The lab started from ClickHouse's
[clickstack-demo-subscription-app](https://github.com/ClickHouse/clickstack-demo-subscription-app),
released under the Apache 2.0 license in `LICENSE`. The original is kept as the `upstream` git
remote, so its fixes can be pulled with `git fetch upstream`.
