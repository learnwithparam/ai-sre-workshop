"""The 3 sigma rule, identical to the analyze_service_anomalies query in workshop/02-anomaly.sql."""

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, pstdev


@dataclass(frozen=True)
class Verdict:
    mean: float
    sigma: float
    bound: float
    current: float
    anomalous: bool


def error_rate(errors: int, requests: int) -> float:
    return errors / requests if requests else 0.0


def three_sigma(baseline: list[float], current: float, min_delta: float) -> Verdict:
    mean = fmean(baseline) if baseline else 0.0
    sigma = pstdev(baseline) if len(baseline) > 1 else 0.0
    bound = mean + 3 * sigma
    return Verdict(mean, sigma, bound, current, current > bound and current - mean >= min_delta)


def clean_baseline(
    buckets: list[tuple[datetime, float]], incidents: list[tuple[datetime, datetime]]
) -> list[float]:
    """Drop buckets that fall inside a past incident, so one outage cannot hide the next."""
    return [rate for at, rate in buckets if not any(start <= at <= end for start, end in incidents)]
