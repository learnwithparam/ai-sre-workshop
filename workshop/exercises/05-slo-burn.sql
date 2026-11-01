-- Exercise 5: the 1 hour burn rate.
-- A 99.5% SLO leaves a budget of 0.5% failed requests. Burn rate is the error rate divided by that budget.
-- Replace the TODO so the query matches the solution block in workshop/05-slo-burn.sql.
-- Check it with: make exercise N=5

-- name: slo_burn
-- example: service=subscription-backend slo=0.995
WITH
    1 - {slo:Float64} AS budget,
    Timestamp > now() - toIntervalHour(1) AS in_1h
SELECT
    ServiceName AS service,
    countIf(in_1h) AS requests_1h,
    round(TODO, 2) AS burn_1h,
    count() AS requests_6h,
    round(countIf(StatusCode = 'Error') / greatest(requests_6h, 1) / budget, 2) AS burn_6h
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND SpanName NOT IN ('GET /health')
  AND Timestamp > now() - toIntervalHour(6)
GROUP BY service
LIMIT 1;
