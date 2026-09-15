-- Module 2: anomaly detection inside the database.

-- name: service_timeseries
-- teaches: bucket request spans into fixed windows; every rate the agent reasons about starts here.
-- example: service=subscription-backend minutes=15 bucket_s=30
SELECT
    toStartOfInterval(Timestamp, toIntervalSecond({bucket_s:UInt32})) AS bucket,
    count() AS requests,
    countIf(StatusCode = 'Error') AS errors,
    round(errors / requests, 4) AS error_rate,
    round(quantile(0.95)(Duration) / 1e6, 1) AS p95_ms
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND SpanName NOT IN ('GET /health')
  AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY bucket
ORDER BY bucket
LIMIT 1000;

-- name: analyze_service_anomalies
-- teaches: mean plus three standard deviations over a trailing baseline, compared with the last minute.
-- The floor (min_delta) stops a silent baseline from alerting on a single failed request.
-- example: baseline_minutes=10 min_delta=0.05
WITH buckets AS (
    SELECT
        ServiceName AS service,
        toStartOfInterval(Timestamp, toIntervalSecond(10)) AS bucket,
        countIf(StatusCode = 'Error') / count() AS error_rate,
        quantile(0.95)(Duration) / 1e6 AS p95_ms,
        count() AS requests
    FROM default.otel_traces
    WHERE SpanKind = 'Server'
      AND SpanName NOT IN ('GET /health', '/')
      AND Timestamp > now() - toIntervalMinute({baseline_minutes:UInt32} + 1)
    GROUP BY service, bucket
)
SELECT
    service,
    round(avgIf(error_rate, bucket < now() - INTERVAL 60 SECOND), 4) AS baseline_mean,
    round(stddevPopIf(error_rate, bucket < now() - INTERVAL 60 SECOND), 4) AS baseline_sigma,
    round(baseline_mean + 3 * baseline_sigma, 4) AS bound,
    round(avgIf(error_rate, bucket >= now() - INTERVAL 60 SECOND), 4) AS current_error_rate,
    round(avgIf(p95_ms, bucket >= now() - INTERVAL 60 SECOND), 1) AS current_p95_ms,
    round(avgIf(p95_ms, bucket < now() - INTERVAL 60 SECOND), 1) AS baseline_p95_ms,
    sumIf(requests, bucket >= now() - INTERVAL 60 SECOND) AS current_requests,
    current_error_rate > bound AND current_error_rate - baseline_mean >= {min_delta:Float64} AS anomalous
FROM buckets
GROUP BY service
ORDER BY anomalous DESC, current_error_rate DESC
LIMIT 50;

-- name: error_rate_window
-- teaches: the detector's input. Buckets keep their timestamps, so application code can drop the
-- ones that fall inside past incidents before computing a baseline.
-- example: service=subscription-backend baseline_minutes=15
WITH buckets AS (
    SELECT
        toStartOfInterval(Timestamp, toIntervalSecond(10)) AS bucket,
        countIf(StatusCode = 'Error') AS errors,
        count() AS requests
    FROM default.otel_traces
    WHERE ServiceName = {service:String}
      AND SpanKind = 'Server'
      AND SpanName NOT IN ('GET /health')
      AND Timestamp > now() - toIntervalMinute({baseline_minutes:UInt32} + 1)
    GROUP BY bucket
)
SELECT
    arraySort(groupArrayIf((bucket, errors / requests), bucket < now() - INTERVAL 60 SECOND)) AS baseline,
    sumIf(errors, bucket >= now() - INTERVAL 60 SECOND) AS current_errors,
    sumIf(requests, bucket >= now() - INTERVAL 60 SECOND) AS current_requests
FROM buckets
LIMIT 1;

-- name: create_service_minute_table
-- teaches: an AggregatingMergeTree keeps partial aggregates, so the view stays tiny and exact.
CREATE TABLE IF NOT EXISTS sre.service_minute
(
    ServiceName LowCardinality(String),
    minute DateTime,
    requests AggregateFunction(count),
    errors AggregateFunction(countIf, UInt8),
    p95 AggregateFunction(quantile(0.95), UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (ServiceName, minute)
TTL minute + INTERVAL 30 DAY;

-- name: create_service_minute_view
-- teaches: a materialized view runs on every insert into otel_traces, so rates are ready before anyone asks.
CREATE MATERIALIZED VIEW IF NOT EXISTS sre.service_minute_mv TO sre.service_minute AS
SELECT
    ServiceName,
    toStartOfMinute(Timestamp) AS minute,
    countState() AS requests,
    countIfState(StatusCode = 'Error') AS errors,
    quantileState(0.95)(Duration) AS p95
FROM default.otel_traces
WHERE SpanKind = 'Server'
GROUP BY ServiceName, minute;

-- name: service_minute_rates
-- teaches: reading the view back with -Merge combinators, over a whole day in milliseconds.
-- example: service=subscription-backend minutes=60
SELECT
    minute,
    countMerge(requests) AS requests,
    countIfMerge(errors) AS errors,
    round(errors / requests, 4) AS error_rate,
    round(quantileMerge(0.95)(p95) / 1e6, 1) AS p95_ms
FROM sre.service_minute
WHERE ServiceName = {service:String} AND minute > now() - toIntervalMinute({minutes:UInt32})
GROUP BY minute
ORDER BY minute
LIMIT 1440;
