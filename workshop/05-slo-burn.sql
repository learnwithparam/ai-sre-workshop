-- Module 5: how fast is the error budget burning?
-- A 99.5% SLO over 30 days leaves a budget of 0.5% failed requests. Burn rate is the observed
-- error rate divided by that budget: 1.0 spends the budget exactly on schedule, 14 empties it in two days.

-- name: slo_burn
-- teaches: burn rate over a short and a long window. Both high means a real, ongoing burn; only the
-- short one high is a blip that has already stopped.
-- example: service=subscription-backend slo=0.995
WITH
    1 - {slo:Float64} AS budget,
    Timestamp > now() - toIntervalHour(1) AS in_1h
SELECT
    ServiceName AS service,
    countIf(in_1h) AS requests_1h,
    round(countIf(in_1h AND StatusCode = 'Error') / greatest(requests_1h, 1) / budget, 2) AS burn_1h,
    count() AS requests_6h,
    round(countIf(StatusCode = 'Error') / greatest(requests_6h, 1) / budget, 2) AS burn_6h
FROM default.otel_traces
WHERE ServiceName = {service:String}
  AND SpanKind = 'Server'
  AND SpanName NOT IN ('GET /health')
  AND Timestamp > now() - toIntervalHour(6)
GROUP BY service
LIMIT 1;
