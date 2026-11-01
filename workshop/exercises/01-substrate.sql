-- Exercise 1: count the failing spans per service.
-- Replace the TODO so the query matches the solution block of the same name in workshop/01-substrate.sql.
-- Check it with: make exercise N=1

-- name: list_services
-- example: minutes=60
SELECT
    ServiceName AS service,
    count() AS spans,
    countIf(TODO) AS error_spans,
    groupUniqArray(5)(ResourceAttributes['service.version']) AS releases,
    min(Timestamp) AS first_seen,
    max(Timestamp) AS last_seen
FROM default.otel_traces
WHERE Timestamp > now() - toIntervalMinute({minutes:UInt32})
GROUP BY service
ORDER BY spans DESC
LIMIT 50;
