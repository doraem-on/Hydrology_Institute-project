"""Paired uncertainty for Gandak and decision-cost sensitivity for the Potomac."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from hydrology.gandak_warning import METHODS


def paired_intervals(frame):
    rng = np.random.default_rng(20261110)
    rows = []
    for h in (6, 12, 24, 48, 72):
        subset = frame[frame.lead_h == h].set_index("issue_time")
        for reference in ["persistence", "barrage"]:
            delta = ((subset.combined - subset.observed).abs()
                     - (subset[reference] - subset.observed).abs())
            daily = delta.resample("D").agg(["sum", "count"])
            n = len(daily)
            starts = rng.integers(n, size=(2000, (n + 2) // 3))
            idx = ((starts[:, :, None] + np.arange(3)) % n).reshape(2000, -1)[:, :n]
            mean = daily["sum"].to_numpy()[idx].sum(axis=1) / daily["count"].to_numpy()[idx].sum(axis=1)
            lo, hi = np.percentile(mean, [2.5, 97.5])
            rows.append(dict(lead_h=h, reference=reference, combined_minus_reference_mae=delta.mean(),
                             lower95=lo, upper95=hi, calendar_days=n))
    return pd.DataFrame(rows)


def decision_costs():
    frame = pd.read_csv("results/decision_replay_20261027/daily_decisions.csv", parse_dates=["date"])
    rows = []
    for year, part in [("all", frame), *list(frame.groupby(frame.date.dt.year))]:
        means = part.groupby("policy")[["overcommitment_m3", "unmet_demand_m3"]].mean()
        baseline, cautious = means.loc["bma_mean"], means.loc["bma_lower_5pct"]
        avoided = baseline.overcommitment_m3 - cautious.overcommitment_m3
        extra = cautious.unmet_demand_m3 - baseline.unmet_demand_m3
        rows.append(dict(period=year, avoided_excess_m3_per_day=avoided,
                         extra_unmet_m3_per_day=extra, break_even_cost_ratio=extra / avoided))
    return pd.DataFrame(rows)


def interval_by_flow():
    root = Path("results/baseline_seed42")
    calibration = pd.read_csv(root / "calibration_predictions.csv")
    heldout = pd.read_csv(root / "test_predictions.csv")
    limits = np.expm1(calibration.observed_log1p_cms).quantile([0.1, 0.9]).to_numpy()
    groups = pd.cut(heldout.persistence_cms, [-np.inf, *limits, np.inf],
                    labels=["low", "middle", "high"])
    rows = []
    for group, sample in heldout.groupby(groups, observed=True):
        below = sample.observed_cms < sample.bma_lower90_cms
        above = sample.observed_cms > sample.bma_upper90_cms
        rows.append(dict(last_flow_band=group, lower_cut_m3s=limits[0], upper_cut_m3s=limits[1],
                         days=len(sample), coverage=(~(below | above)).mean(),
                         misses_below=below.sum(), misses_above=above.sum(),
                         mean_width_m3s=(sample.bma_upper90_cms-sample.bma_lower90_cms).mean()))
    return pd.DataFrame(rows)


def main():
    folder = Path("results/gandak_warning")
    frame = pd.read_csv(folder / "forecasts.csv.gz", parse_dates=["issue_time"])
    paired_intervals(frame).to_csv(folder / "paired_intervals.csv", index=False, float_format="%.4f")
    decision_costs().to_csv(Path("results/decision_replay_20261027/policy_cost_sensitivity.csv"),
                            index=False, float_format="%.4f")
    interval_by_flow().to_csv("results/baseline_seed42/interval_coverage_by_flow.csv",
                              index=False, float_format="%.4f")
    event = pd.read_csv(folder / "september_forecast.csv")
    scores = pd.read_csv(folder / "scores.csv")
    labels = dict(observed="Recorded inflow", persistence="Last reading", barrage="Barrage history",
                  gauge="+ Devghat", rain="+ Rain", combined="+ Devghat and rain")
    colours = dict(observed="black", persistence="#78522b", barrage="#64748b", gauge="#356a9d",
                   rain="#ab5475", combined="#007568")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for name in ["observed", "persistence", "barrage", "combined"]:
        axes[0].plot(event.lead_h, event[name], label=labels[name], color=colours[name],
                     linestyle="--" if name=="persistence" else "-")
    for name in METHODS:
        line = scores[scores.method == name]
        axes[1].plot(line.lead_h, line.mae, label=labels[name], color=colours[name])
    for axis, title, ylabel in zip(axes, ["Forecast issued 27 September at 14:00 IST", "Error on matched test hours"],
                                    ["Inflow (m³/s)", "Mean absolute error (m³/s)"]):
        axis.set(xlabel="Hours ahead", ylabel=ylabel, title=title)
        axis.legend(frameon=False, fontsize=8)
        axis.grid(axis="y", alpha=.18)
    fig.savefig(folder / "warning_comparison.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
