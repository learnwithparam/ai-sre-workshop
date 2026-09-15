-- Module 1: the telemetry substrate.
-- Every query here is a named block. sre-control loads the same blocks for its MCP tools, so the
-- SQL you write in the workshop is the SQL the agent runs. `-- example:` gives the values
-- `make e2e` binds when it runs every block as the read-only sre_agent user.

-- name: list_tables
-- teaches: ClickStack stores each signal in its own MergeTree table; parts and rows are cheap to inspect.
SELECT
    table,
    sum(rows) AS rows,
    formatReadableSize(sum(data_compressed_bytes)) AS compressed,
    round(sum(data_uncompressed_bytes) / greatest(sum(data_compressed_bytes), 1), 1) AS ratio
FROM system.parts
WHERE database = 'default' AND active AND table LIKE 'otel_%'
GROUP BY table
ORDER BY rows DESC
LIMIT 20;

-- name: list_services
-- teaches: ORDER BY (ServiceName, SpanName, Timestamp) makes a per-service scan read few granules.
-- example: minutes=60
SELECT
    ServiceName AS service,
    count() AS spans,
    countIf(StatusCode = 'Error') AS error_spans,
    groupUniqArray(5)(ResourceAttributes['service.version']) AS releases,
    min(Timestamp) AS first_seen,
    max(Timestamp) AS last_seen
FROM default.otel_traces
WHERE Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY service
ORDER BY spans DESC
LIMIT 50;

-- name: latency_percentiles
-- teaches: quantiles over every unsampled span, per endpoint, in one pass.
-- example: service=subscription-backend minutes=30
SELECT
    SpanName AS endpoint,
    count() AS requests,
    round(quantile(0.50)(Duration) / 1e6, 1) AS p50_ms,
    round(quantile(0.95)(Duration) / 1e6, 1) AS p95_ms,
    round(quantile(0.99)(Duration) / 1e6, 1) AS p99_ms,
    round(countIf(StatusCode = 'Error') / count(), 4) AS error_rate
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY endpoint
ORDER BY requests DESC
LIMIT 50;
