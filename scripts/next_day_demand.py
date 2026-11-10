"""Train a calendar-only next-day withdrawal forecast, then reveal observed outcomes."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.decision_replay import replay
from hydrology.withdrawals import demand_records, fit_calendar, forecast

OUT = Path("results/decision_replay_both")
HISTORY = Path("data/raw/usgs/little_falls_daily_2010_2019.rdb")
CUTOFF = pd.Timestamp("2019-10-31")


def main(issue):
    forecasts = pd.read_csv("results/baseline_seed42/test_predictions.csv", parse_dates=["date"])
    dates = pd.date_range("2010-01-01", "2019-12-31")
    history = demand_records(pd.DataFrame({"date": dates.strftime("%Y-%m-%d")}), HISTORY)
    recent = pd.read_csv("results/potomac_diversions/diversion_by_date.csv", parse_dates=["date"])
    history["date"] = pd.to_datetime(history.date)
    records = pd.concat([history, recent]).set_index("date").sort_index()
    observed = records.diversion_m3_day.where(records.quality == "included")
    coef, constant, n = fit_calendar(observed, CUTOFF)
    f = forecasts.copy()
    f["predicted_demand_m3"] = forecast(f.date, coef)
    f["constant_m3"] = constant
    f["issue_date"] = f.date - pd.Timedelta(days=1)
    # Reveal verification values only after all predictions have been made.
    f["actual_withdrawal_m3"] = observed.reindex(f.date).to_numpy()
    f.to_csv(OUT / "potomac_demand_forecasts.csv", index=False, float_format="%.5f")
    valid = f.dropna(subset=["actual_withdrawal_m3"])
    scores = []
    for policy, col in [("calendar","predicted_demand_m3"), ("training_mean","constant_m3")]:
        error = valid[col] - valid.actual_withdrawal_m3
        scores.append(dict(policy=policy, trained_through=CUTOFF.date(), training_days=n,
            forecast_days=len(f), verified_days=len(valid), mae_m3_day=error.abs().mean(),
            rmse_m3_day=np.sqrt((error**2).mean()), mean_bias_m3_day=error.mean()))
    pd.DataFrame(scores).to_csv(OUT / "potomac_demand_scores.csv", index=False, float_format="%.2f")
    summaries, traces = [], []
    for name, column in [("calendar","predicted_demand_m3"), ("constant","constant_m3")]:
        daily, summary = replay(valid, demand_m3=valid[[column]].to_numpy(),
            realized_demand_m3=valid.actual_withdrawal_m3.to_numpy(),
            environmental_flow_cms=20., diversion_fraction=.1)
        summaries.extend(dict(demand_rule=name, **row) for row in summary)
        traces.append(daily.assign(demand_rule=name))
    pd.DataFrame(summaries).to_csv(OUT / "potomac_policy_scores.csv", index=False, float_format="%.6f")
    pd.concat(traces).to_csv(OUT / "potomac_daily_decisions.csv.gz", index=False, float_format="%.3f",
                            compression={"method":"gzip","mtime":0})
    # A separately labelled, unverified forecast using only mature archive dates.
    if issue <= f.date.max() + pd.Timedelta(days=62):
        raise ValueError("Prospective issue must follow the archived test and reporting buffer")
    updated, _, count = fit_calendar(observed, f.date.max())
    target = issue + pd.Timedelta(days=1)
    pd.DataFrame([dict(issue_date=issue.date(), target_date=target.date(), training_days=count,
        last_training_observation=observed.dropna().index.max().date(),
        predicted_withdrawal_m3=forecast([target],updated)[0])]).to_csv(
            OUT / "potomac_next_day.csv", index=False, float_format="%.2f")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-date", type=pd.Timestamp, default=pd.Timestamp("2026-11-10"))
    main(parser.parse_args().issue_date)
