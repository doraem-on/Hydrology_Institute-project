import numpy as np
import pandas as pd

from hydrology.gandak_warning import gauge_at_issue, rain_features, warning_audit, METHODS


def test_delayed_or_out_of_order_gauge_and_stale_reading():
    clock = pd.date_range("2026-09-01", periods=6, freq="h", tz="UTC")
    rows = pd.DataFrame({"observed": [clock[0], clock[1], clock[0]],
                         "available": [clock[0], clock[2], clock[3]], "level_m": [4., 8., 5.]})
    result = gauge_at_issue(rows, clock)
    np.testing.assert_allclose(result, [4, 4, 8, 8, np.nan, np.nan], equal_nan=True)


def test_unreleased_rain_cycle_and_future_hours_are_excluded():
    cycles = pd.date_range("2026-09-01", periods=2, tz="UTC")
    matrix = pd.DataFrame(np.array([np.arange(120), np.full(120, 500.)]), index=cycles)
    issues = pd.DatetimeIndex(["2026-09-02T11:30Z", "2026-09-02T12:30Z"])
    output = rain_features(matrix, issues, 2, delay=12)
    np.testing.assert_allclose(output.rain_to_target, [36 + 37, 1000])


def test_warning_lead_and_false_issues():
    hours = pd.date_range("2026-09-15", periods=100, freq="h")
    q = pd.Series(1., index=hours)
    q.loc[hours[52]:hours[55]] = 20.
    rows = []
    for issue in [hours[25], hours[49], hours[52]]:
        for lead in range(1, 25):
            rows.append(dict(issue_time=issue, lead_h=lead,
                             **{name: (16. if lead==3 else 1.) for name in METHODS}))
    alerts, events = warning_audit(pd.DataFrame(rows), q, 15.)
    assert set(events.first_warning_hours) == {3}
    assert set(alerts.eligible_issues) == {2}
    assert set(alerts.false_alert_issues) == {1}
