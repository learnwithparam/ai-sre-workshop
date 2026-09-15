-- Module 3.3 and Module 4: walk one trace, and prove every claim the agent makes.

-- name: sample_error_traces
-- teaches: evidence is a trace id you can open. Failing requests first, then the slowest, so the
-- agent always has real trace ids to cite.
-- example: service=subscription-backend minutes=60
SELECT
    TraceId AS trace_id,
    SpanName AS endpoint,
    ResourceAttributes['service.version'] AS release,
    round(Duration / 1e6, 1) AS duration_ms,
    StatusMessage AS status_message,
    Timestamp
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND SpanName NOT IN ('GET /health')
  AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
ORDER BY StatusCode = 'Error' DESC, Duration DESC
LIMIT 10;

-- name: get_trace_waterfall
-- teaches: parent and child spans across the browser, Flask and Postgres, ordered by start offset.
-- example: trace_id=@sample_error_traces
SELECT
    SpanId AS span_id,
    ParentSpanId AS parent_span_id,
    ServiceName AS service,
    SpanName AS span,
    SpanKind AS kind,
    round(dateDiff('microsecond', min(Timestamp) OVER (), Timestamp) / 1e3, 1) AS start_offset_ms,
    round(Duration / 1e6, 1) AS duration_ms,
    StatusCode AS status,
    StatusMessage AS status_message,
    SpanAttributes['db.statement'] AS db_statement
FROM default.otel_traces
WHERE TraceId = {trace_id:String}
ORDER BY Timestamp
LIMIT 200;

-- name: errors_by_release
-- teaches: break the failure down by service.version; a change that lines up with a release is a lead.
-- example: service=subscription-backend minutes=30
SELECT
    ResourceAttributes['service.version'] AS release,
    min(Timestamp) AS first_seen,
    count() AS requests,
    countIf(StatusCode = 'Error') AS errors,
    round(errors / requests, 4) AS error_rate,
    round(quantile(0.95)(Duration) / 1e6, 1) AS p95_ms
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND SpanName NOT IN ('GET /health')
  AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY release
ORDER BY first_seen
LIMIT 20;

-- name: known_trace_ids
-- teaches: grounding. A proposal is refused unless every trace id it cites exists, as a span or,
-- for a request that never finished and so never exported a span, as a correlated log line.
-- example: trace_ids=@sample_error_traces hours=6
SELECT trace_id FROM (
    SELECT DISTINCT TraceId AS trace_id
    FROM default.otel_traces
    WHERE TraceId IN {trace_ids:Array(String)} AND Timestamp > now() - toIntervalHour({hours:UInt32})
    UNION DISTINCT
    SELECT DISTINCT if(TraceId != '', TraceId, LogAttributes['trace_id']) AS trace_id
    FROM default.otel_logs
    WHERE (TraceId IN {trace_ids:Array(String)} OR LogAttributes['trace_id'] IN {trace_ids:Array(String)})
      AND Timestamp > now() - toIntervalHour({hours:UInt32})
)
LIMIT 100;

-- name: trace_logs
-- teaches: logs correlated to one trace. The Go service writes the id to a log attribute, Python to
-- the TraceId column, so the query reads both.
-- example: trace_id=@sample_error_traces
SELECT
    Timestamp,
    ServiceName AS service,
    SeverityText AS severity,
    Body AS body
FROM default.otel_logs
WHERE (TraceId = {trace_id:String} OR LogAttributes['trace_id'] = {trace_id:String})
  AND Timestamp > now() - INTERVAL 1 DAY
ORDER BY Timestamp
LIMIT 100;

-- name: service_releases
-- teaches: grounding. The service and release a proposal names must have reported telemetry.
-- example: service=subscription-backend hours=6
SELECT DISTINCT ResourceAttributes['service.version'] AS release
FROM default.otel_traces
WHERE ServiceName = {service:String} AND Timestamp > now() - toIntervalHour({hours:UInt32})
LIMIT 50;
