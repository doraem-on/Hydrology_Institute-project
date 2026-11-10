"""Historical Gandak Barrage inflow pilot. Run from the repository root."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RESULTS = Path("results/gandak_hourly")
TEST_START = pd.Timestamp("2026-09-16")
EVENT_ISSUE = pd.Timestamp("2026-09-27 14:00")


def barrage_features(folder=RESULTS):
    raw = pd.read_csv(folder / "source_inflow.csv", parse_dates=["timestamp"])
    q = raw.set_index("timestamp").inflow_m3s.sort_index()
    if q.index.has_duplicates or (q.index != q.index.floor("h")).any():
        raise ValueError("Expected unique whole-hour timestamps for one station")
    q = q.asfreq("h")
    # Quarantine one documented source anomaly without estimating a replacement.
    suspect = pd.Timestamp("2026-08-03 01:00")
    if q.get(suspect) == 339091.0:
        q.at[suspect] = np.nan
    q = q.where(q.ge(0) & np.isfinite(q))
    z = np.log1p(q)
    features = pd.DataFrame({"level": z})
    for lag in (1, 3, 6, 12, 24):
        features[f"change_{lag}h"] = z - z.shift(lag)
    # Only issue a forecast after 25 consecutive observed clock hours.
    features = features.where(q.rolling(25).count().eq(25), axis=0)
    return q, features


def fit_ridge(features, z, target, train):
    x = features[train]
    # Scale using training data. Fit the log change from issue time directly
    # for each horizon, with a fixed ridge penalty and unpenalized intercept.
    mean, std = x.mean(), x.std().replace(0, 1.0)
    x = ((x - mean) / std).to_numpy()
    y = (np.log1p(target[train]) - z[train]).to_numpy()
    weights = np.linalg.solve(x.T @ x + np.eye(x.shape[1]), x.T @ (y - y.mean()))
    return dict(features=list(features.columns), mean=mean.tolist(), std=std.tolist(),
                weights=weights.tolist(), intercept=float(y.mean()))


def apply_ridge(model, features, z):
    x = features.loc[:, model["features"]].to_numpy()
    change = ((x - model["mean"]) / model["std"]) @ model["weights"] + model["intercept"]
    return np.maximum(0, np.expm1(z.to_numpy() + change))


def predict_ridge(features, z, target, train, test):
    model = fit_ridge(features, z, target, train)
    return apply_ridge(model, features[test], z[test])


def run(folder=RESULTS):
    q, features = barrage_features(folder)
    z = np.log1p(q)
    forecasts = []
    scores = []
    for h in range(1, 73):
        lead = pd.Timedelta(hours=h)
        target = q.shift(-h)
        usable = features.notna().all(axis=1) & target.notna()
        train = usable & (q.index + lead < TEST_START)
        test = usable & (q.index >= TEST_START)
        prediction = predict_ridge(features, z, target, train, test)
        out = pd.DataFrame({"issue_time": q.index[test], "lead_h": h,
                            "valid_time": q.index[test] + lead,
                            "observed_m3s": target[test].to_numpy(),
                            "ridge_m3s": prediction, "persistence_m3s": q[test].to_numpy()})
        forecasts.append(out)
        result = {"lead_h": h, "training_pairs": int(train.sum()), "test_pairs": len(out)}
        for method in ("ridge", "persistence"):
            error = out[f"{method}_m3s"] - out.observed_m3s
            result[f"{method}_mae"] = error.abs().mean()
            result[f"{method}_rmse"] = np.sqrt((error ** 2).mean())
        scores.append(result)
    predictions = pd.concat(forecasts, ignore_index=True)
    predictions.to_csv(folder / "heldout_predictions.csv.gz", index=False, float_format="%.4f",
                       compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(scores).to_csv(folder / "metrics_by_lead.csv", index=False, float_format="%.4f")
    event = predictions.loc[predictions.issue_time == EVENT_ISSUE].sort_values("lead_h")
    if len(event) != 72:
        raise ValueError("Event comparison requires all 72 verified hourly targets")
    event.to_csv(folder / "september_event.csv", index=False, float_format="%.2f")
    fig, ax = plt.subplots(figsize=(8, 4))
    for name, label, color, style in (("observed", "Archived inflow", "black", "-"),
                                      ("ridge", "Lagged-flow model", "#007d80", "--"),
                                      ("persistence", "Last reading", "#996633", ":")):
        ax.plot(event.lead_h, event[f"{name}_m3s"], label=label, color=color, ls=style)
    ax.set(xlabel="Hours after forecast issue", ylabel="Barrage inflow (m³/s)",
           title="Gandak Barrage · historical forecast issued 27 Sep 2026 at 14:00")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(folder / "september_event.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    run()
