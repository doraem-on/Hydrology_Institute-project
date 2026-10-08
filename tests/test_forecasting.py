import numpy as np
import pandas as pd
import pytest
import torch
from hydrology.bma import ForecastBMA
from hydrology.data import CFS_TO_CMS, make_windows, parse_usgs
from hydrology.models import NAMES, build_model
from hydrology.train import metrics


def synthetic_frame():
    return pd.DataFrame({"date": pd.date_range("2000-01-01", periods=200),
                         "discharge_cms": 10+np.sin(np.arange(200)/10)})


def windowed(frame):
    return make_windows(frame, 7, "2000-03-01", "2000-04-01", "2000-05-01")


def test_windows_are_causal_and_scaling_uses_train_only():
    frame = synthetic_frame()
    result = windowed(frame)
    changed = frame.copy()
    changed.loc[190:, "discharge_cms"] = 100000
    other = windowed(changed)
    assert result["mean"] == other["mean"]
    assert result["scale"] == other["scale"]
    np.testing.assert_array_equal(result["x"][:183], other["x"][:183])
    reconstructed = result["x"][0, :, 0]*result["scale"]+result["mean"]
    np.testing.assert_allclose(reconstructed, np.log1p(frame.discharge_cms[:7]), rtol=1e-6)
    assert result["dates"][0] == frame.date.iloc[7]
    assert np.all(np.sum(list(result["masks"].values()), axis=0) == 1)


def test_missing_days_and_values_are_not_bridged():
    frame = synthetic_frame().drop(index=80).reset_index(drop=True)
    frame.loc[100, "discharge_cms"] = np.nan
    result = windowed(frame)
    for date in result["dates"]:
        rows = frame[(frame.date >= date-pd.Timedelta(days=7)) & (frame.date <= date)]
        assert len(rows) == 8
        assert rows.discharge_cms.notna().all()


@pytest.mark.parametrize("name", NAMES)
def test_model_gradients_and_batch_independence(name):
    torch.manual_seed(1)
    model = build_model(name, hidden=8, lookback=7)
    x = torch.randn(3, 7, 3)
    output = model(x)
    assert output.shape == (3,)
    output.square().mean().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    model.eval()
    with torch.no_grad():
        torch.testing.assert_close(model(x)[:1], model(x[:1]), rtol=1e-4, atol=1e-5)


def test_bma_normalization_em_and_intervals():
    rng = np.random.default_rng(4)
    signal = rng.normal(2, 0.3, 500)
    forecasts = np.column_stack([signal, rng.normal(2, 0.3, 500)])
    y = signal+rng.normal(0, 0.1, 500)
    bma = ForecastBMA().fit(forecasts, y)
    assert np.isclose(bma.weights.sum(), 1)
    assert (bma.weights >= 0).all() and bma.weights[0] > 0.8
    assert min(np.diff(bma.log_likelihood)) >= -1e-7
    low = bma.quantile_discharge(forecasts, 0.05)
    high = bma.quantile_discharge(forecasts, 0.95)
    assert (low >= 0).all() and (high >= low).all()
    assert np.isfinite(bma.mean_discharge(forecasts)).all()


def test_censored_bma_mean_matches_monte_carlo():
    bma = ForecastBMA()
    bma.intercept, bma.slope = np.array([-0.4, 0.3]), np.zeros(2)
    bma.weights, bma.variance = np.array([0.3, 0.7]), 0.2
    rng = np.random.default_rng(4)
    k = rng.choice(2, 200000, p=bma.weights)
    samples = np.maximum(np.expm1(rng.normal(bma.intercept[k], np.sqrt(bma.variance))), 0)
    assert abs(samples.mean()-bma.mean_discharge(np.zeros((1, 2)))[0]) < 0.005


def test_metrics_known_values():
    y = np.array([1., 2., 3.])
    assert metrics(y, y)["nse"] == 1
    assert metrics(y, np.full(3, 2.))["nse"] == 0
    assert metrics(np.ones(3), np.ones(3))["nse"] is None


def test_usgs_rejects_unapproved_and_sentinel_values():
    payload = {"value": {"timeSeries": [{"sourceInfo": {"siteCode": [{"value": "x"}], "siteName": "Test"},
                "variable": {"variableCode": [{"value": "00060"}], "unit": {"unitCode": "ft3/s"}, "noDataValue": -999999},
                "values": [{"value": [{"dateTime": f"2000-01-0{i+1}T00:00:00", "value": str(v), "qualifiers": flags}
                                      for i,(v,flags) in enumerate([(10,["A"]),(-999999,["A"]),(20,["P"])])]}]}]}}
    frame, _ = parse_usgs(payload, "x")
    assert frame.discharge_cms.iloc[0] == 10*CFS_TO_CMS
    assert frame.discharge_cms.iloc[1:].isna().all()
