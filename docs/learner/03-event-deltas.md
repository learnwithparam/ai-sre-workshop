# 03 Find what changed

## Why compare two windows

A failing service writes many log lines. Most of them also show up on a good day. The line that matters is the one that is new. So you compare the incident window with the same stretch of time just before it.

Complementary materials:

- Book: [Effective troubleshooting](https://sre.google/sre-book/effective-troubleshooting/). Ask "what changed?" first, then test one idea at a time.
- Docs: [Logs](https://opentelemetry.io/docs/concepts/signals/logs/). How a log line carries its service and its trace id.
- Docs: [replaceRegexpAll](https://clickhouse.com/docs/sql-reference/functions/string-replace-functions#replaceregexpall). The function that masks numbers and ids in this lesson.

## Goal

You can mark each log pattern as new or old, and rank the new ones first.

## Before

An incident opens. You search the logs for "error" and get ten thousand lines. Most say the same thing with a different number in them. Some have shown up every day for a year. You read the first page, see nothing new, and give up.

![Event deltas: log lines from otel_logs are masked so numbers become N, then counted in the window before and the incident window. Ranking puts new patterns first, and the top row is a new pattern, connection pool full. A second path groups failed spans by release and finds that v2 fails and v1 is clean. The AI SRE cites both.](../images/diagrams/event-deltas.svg)

Two questions find the cause fast:

1. **Mask the lines.** Numbers, ids and emails become `N`, so lines fold into a few patterns.
2. **Count in two windows.** Once in the incident window, and once in a window of the same length just before it.
3. **Put new first.** A pattern with no count before is new. Then sort by growth.
4. **Split errors by release.** If v2 fails and v1 does not, the release is the change.

## Starting point

You finished [Spot an odd minute](02-anomaly.md). You edit `workshop/exercises/03-event-deltas.sql`.

## Step 1: See how a line becomes a pattern

Open `workshop/exercises/03-event-deltas.sql`. The `pattern` at the top runs three replaces on each log line:

- A time in square brackets becomes `[ts]`.
- A long hex id or an email becomes `<id>`.
- Any other number becomes `N`.

So `pool exhausted: 20 of 20` becomes `pool exhausted: N of N`. Ten thousand lines fold into a few shapes you can read.

**Verify:** you can say what `request 4182 took 950 ms` turns into.

## Step 2: Fill in the TODO

Find this line:

```sql
TODO AS is_new,
```

The query already counts `incident` and `baseline` for each pattern. A pattern is new when it shows up in the incident window and never in the baseline.

```bash
make exercise N=3
```

Expect: `match: get_event_deltas returns the same N row(s) as the solution`, where N is the number of patterns.

**Verify:** the check prints `match:`. Look at the `ORDER BY` line: new patterns first, then errors, then the biggest growth.

## Step 3: Read the release split

Open [workshop/04-trace-graph.sql](../../workshop/04-trace-graph.sql) and find `errors_by_release`. It runs the same idea on spans. It groups failed spans by `service.version`. When one release fails and the other does not, you know which change to undo.

**Verify:** you can name the column that holds the release.

## Use it

In the live incident, the agent runs your query as `get_event_deltas`. Here is its reply in LibreChat.

![The agent's reply: an 11 percent error rate, p95 of 1066 ms against 239 ms. Release v2 fails 14.7 percent of the time and v1 fails none. Only POST /api/subscribe fails. A new log pattern, connection pool exhausted, shows up 102 times. Failing trace ids follow.](../../evidence/screens/chat-proposal.png)

Find the two clues from this lesson in it:

- The new pattern: `connection pool exhausted: N of N connections in use`. It was not there before.
- The release split: v2 fails about 15 percent of signups, v1 fails none.

HyperDX has the same two views by hand. In Search, the left panel offers **Event Deltas** and **Event Patterns**.

## How to verify you are done

- `make exercise N=3` prints `match:`.
- You can explain why a new pattern beats a loud one.
- You can point at the new pattern and the release split in the agent's reply.

## Wrap-up

New beats loud. Masking turns lines into patterns you can count, and two windows of the same length make the counts fair. The lab also has `event_patterns`, `search_logs` and `stuck_requests` in the same file. `stuck_requests` finds a request that started and never finished. Read more on [event deltas](../walkthrough.md#c-event-delta) and [log patterns](../walkthrough.md#c-log-pattern).

## If you get stuck

The answer is the `get_event_deltas` block in [workshop/03-event-deltas.sql](../../workshop/03-event-deltas.sql).

## Next

[Open one request](04-trace-graph.md).
