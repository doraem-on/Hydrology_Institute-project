import numpy as np
import pandas as pd

from hydrology.decision_replay import replay
from hydrology.withdrawals import fit_calendar, forecast
from hydrology.town_warning_replay import september_timing, verify


def test_target_day_observations_do_not_change_plans_or_demand_fit():
    dates = pd.date_range("2018-01-01", periods=730)
    x = pd.Series(np.arange(len(dates)) + 1e5, index=dates)
    cutoff = dates[499]
    estimate = forecast(dates[500:], fit_calendar(x, cutoff)[0])
    x.loc[dates[500:]] = 0
    np.testing.assert_array_equal(estimate, forecast(dates[500:], fit_calendar(x, cutoff)[0]))

    frame = pd.DataFrame(dict(date=["2025-01-01"], observed_cms=[100.],
        persistence_cms=[80.], bma_mean_cms=[90.], bma_lower90_cms=[70.]))
    opts = dict(demand_m3=[1e5], environmental_flow_cms=0, diversion_fraction=.1)
    full, _ = replay(frame, realized_demand_m3=[2e5], **opts)
    frame["observed_cms"] = 3.
    low, _ = replay(frame, realized_demand_m3=[500.], **opts)
    np.testing.assert_array_equal(full.planned_m3, low.planned_m3)
    assert (low.feasible_delivery_m3 == 500).all()
    assert (low.unmet_demand_m3 == 0).all()
    assert (full.unmet_demand_m3 == 1e5).all()


def test_town_replay_keeps_late_and_unassessable_warnings_distinct():
    dates = pd.date_range("2026-09-24", periods=96, freq="h")
    stage = pd.Series(94., index=dates)
    stage.iloc[32:] = 95.1
    decisions = pd.DataFrame({"model": dates >= dates[33], "last_reading": dates >= dates[35]}, index=dates)
    timing = september_timing(decisions, stage, {"warning":95})
    assert timing.hours_before_crossing.tolist() == [-1, -3]
    audit, _ = verify(decisions, stage, {"warning":95})
    assert audit.missed.tolist() == [1, 1]
    decisions = decisions.astype("boolean")
    decisions.loc[dates[8:32], "model"] = pd.NA
    audit, _ = verify(decisions, stage, {"warning":95})
    assert audit.assessable_onsets.tolist() == [0, 0]
