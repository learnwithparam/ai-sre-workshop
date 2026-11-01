-- Exercise 4: show failing requests first, then the slowest.
-- Replace the TODO so the query matches the solution block of the same name in workshop/04-trace-graph.sql.
-- Check it with: make exercise N=4

-- name: sample_error_traces
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
ORDER BY TODO
LIMIT 10;
