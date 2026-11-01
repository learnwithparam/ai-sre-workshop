-- Exercise 3: flag a log pattern that did not exist before the incident.
-- Replace the TODO so the query matches the solution block of the same name in workshop/03-event-deltas.sql.
-- Check it with: make exercise N=3

-- name: get_event_deltas
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
    TODO AS is_new,
    any(if(TraceId != '', TraceId, LogAttributes['trace_id'])) AS example_trace_id
FROM default.otel_logs
WHERE ServiceName = {service:String} AND Timestamp >= baseline_start
GROUP BY severity, pattern
HAVING incident > 0
ORDER BY is_new DESC, severity = 'error' DESC, delta DESC
LIMIT 20;
