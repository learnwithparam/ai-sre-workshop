-- Exercise 2: the error rate per time bucket.
-- Replace the TODO so the query matches the solution block of the same name in workshop/02-anomaly.sql.
-- Check it with: make exercise N=2

-- name: service_timeseries
-- example: service=subscription-backend minutes=15 bucket_s=30
SELECT
    toStartOfInterval(Timestamp, toIntervalSecond({bucket_s:UInt32})) AS bucket,
    count() AS requests,
    countIf(StatusCode = 'Error') AS errors,
    round(TODO, 4) AS error_rate,
    round(quantile(0.95)(Duration) / 1e6, 1) AS p95_ms
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND SpanName NOT IN ('GET /health')
  AND Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY bucket
ORDER BY bucket
LIMIT 1000;
