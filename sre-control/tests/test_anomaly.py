"""The 3 sigma rule the detector and the workshop SQL both use."""

from sre_control.anomaly import error_rate, three_sigma

STEADY_RATES = [0.010, 0.012, 0.009, 0.011, 0.010, 0.013, 0.008, 0.010, 0.011, 0.012]


def test_spike_is_flagged():
    verdict = three_sigma(STEADY_RATES, current=0.34, min_delta=0.05)
    assert verdict.anomalous
    assert 0.010 < verdict.mean < 0.011
    assert verdict.bound < 0.02


def test_ramp_is_not_flagged():
    # Traffic grows tenfold while the share of failures holds, so the rate signal stays quiet.
    baseline = [error_rate(errors=n // 100, requests=n) for n in range(100, 1100, 100)]
    assert not three_sigma(baseline, current=error_rate(errors=15, requests=1500), min_delta=0.05).anomalous


def test_blip_over_a_silent_baseline_needs_the_floor():
    # A zero-variance baseline makes any error exceed mean + 3 sigma; the floor keeps one error quiet.
    assert not three_sigma([0.0] * 10, current=0.02, min_delta=0.05).anomalous
    assert three_sigma([0.0] * 10, current=0.30, min_delta=0.05).anomalous


def test_error_rate_of_no_traffic_is_zero():
    assert error_rate(errors=0, requests=0) == 0.0
