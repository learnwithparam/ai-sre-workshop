-- Module 3: root cause localization with event deltas.
-- A pattern is a log body with its numbers, hex ids, emails and timestamps masked, so ten thousand
-- lines collapse into the handful of shapes a human would recognise.

-- name: get_event_deltas
-- teaches: compare the incident window with the same length of time just before it, and rank
-- what is new, then what grew most. New error signatures float to the top; steady background noise cancels out.
-- example: service=subscription-backend incident_minutes=5
WITH
    replaceRegexpAll(
        replaceRegexpAll(replaceRegexpAll(Body, '\\[[^\\]]*\\]', '[ts]'), '[0-9a-f]{16,}|\\S+@\\S+', '<id>'),
        '\\d+(\\.\\d+)?', 'N'
    ) AS pattern,
    now() - toIntervalMinute({incident_minutes:UInt32}) AS incident_start,
    incident_start - toIntervalMinute({incident_minutes:UInt32}) AS baseline_start
SELECT
    SeverityText AS severity,
    pattern,
    countIf(Timestamp >= incident_start) AS incident,
    countIf(Timestamp < incident_start) AS baseline,
    incident - baseline AS delta,
    baseline = 0 AND incident > 0 AS is_new,
    any(if(TraceId != '', TraceId, LogAttributes['trace_id'])) AS example_trace_id
FROM default.otel_logs
WHERE ServiceName = {service:String} AND Timestamp >= baseline_start
GROUP BY severity, pattern
HAVING incident > 0
ORDER BY is_new DESC, severity = 'error' DESC, delta DESC
LIMIT 20;

-- name: error_span_deltas
-- teaches: the same delta over spans, so a failing endpoint and its status message show up by release.
-- example: service=subscription-backend incident_minutes=5
WITH now() - toIntervalMinute({incident_minutes:UInt32}) AS incident_start
SELECT
    SpanName AS endpoint,
    ResourceAttributes['service.version'] AS release,
    StatusMessage AS status_message,
    countIf(Timestamp >= incident_start AND StatusCode = 'Error') AS incident_errors,
    countIf(Timestamp < incident_start AND StatusCode = 'Error') AS baseline_errors,
    countIf(Timestamp >= incident_start) AS incident_requests,
    any(TraceId) AS example_trace_id
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND Timestamp >= incident_start - toIntervalMinute({incident_minutes:UInt32})
GROUP BY endpoint, release, status_message
HAVING incident_requests > 0
ORDER BY incident_errors - baseline_errors DESC, incident_requests DESC
LIMIT 20;

-- name: event_patterns
-- teaches: cluster a window of logs into patterns with counts, severities and one example each.
-- example: service=docs-loader minutes=10
SELECT
    replaceRegexpAll(
        replaceRegexpAll(replaceRegexpAll(Body, '\\[[^\\]]*\\]', '[ts]'), '[0-9a-f]{16,}|\\S+@\\S+', '<id>'),
        '\\d+(\\.\\d+)?', 'N'
    ) AS pattern,
    count() AS events,
    groupUniqArray(3)(SeverityText) AS severities,
    min(Timestamp) AS first_seen,
    max(Timestamp) AS last_seen,
    any(Body) AS example
FROM default.otel_logs
WHERE ServiceName = {service:String} AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY pattern
ORDER BY events DESC
LIMIT 25;

-- name: search_logs
-- teaches: substring search. hasToken would use the token index but refuses a phrase with spaces,
-- and a model searches in phrases; the service filter on the primary key keeps the scan small.
-- The example searches a phrase every run has, so this block does not depend on a failure being
-- injected first. During an incident the phrase to try is "connection pool".
-- example: service=subscription-backend text=POST /api/subscribe minutes=60
SELECT
    Timestamp,
    SeverityText AS severity,
    Body AS body,
    if(TraceId != '', TraceId, LogAttributes['trace_id']) AS trace_id
FROM default.otel_logs
WHERE ServiceName = {service:String}
  AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
  AND positionCaseInsensitive(Body, {text:String}) > 0
ORDER BY Timestamp DESC
LIMIT 50;

-- name: stuck_requests
-- teaches: an absence is a signal. A request that logged "received" and never "completed", since
-- the service last started, is still hanging. The Flask side never exports its span, so logs are
-- the only witness. The Go service puts the trace id in a log attribute, not the TraceId column.
-- example: service=docs-loader older_than_s=0
WITH (
    SELECT max(Timestamp) FROM default.otel_logs
    WHERE ServiceName = {service:String} AND Body LIKE '** Service Started%'
) AS started_at
SELECT
    count() AS stuck,
    max(age_s) AS oldest_s,
    groupArray(5)(trace_id) AS example_trace_ids
FROM (
    SELECT
        LogAttributes['trace_id'] AS trace_id,
        dateDiff('second', min(Timestamp), now()) AS age_s,
        countIf(Body LIKE 'request received:%') AS received,
        countIf(Body LIKE 'request completed:%') AS completed
    FROM default.otel_logs
    WHERE ServiceName = {service:String}
      AND Timestamp > greatest(started_at, now() - INTERVAL 30 MINUTE)
      AND trace_id != ''
    GROUP BY trace_id
    HAVING received > completed AND age_s >= {older_than_s:UInt32}
)
LIMIT 1;
