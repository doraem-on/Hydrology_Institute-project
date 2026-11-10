"""Replay the saved forecasts against reported municipal diversions at Little Falls."""
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.decision_replay import replay

RAW = Path("data/raw/usgs/little_falls_daily_2020_2025.rdb")
OUT = Path("results/potomac_diversions")
CFS_TO_M3_DAY = 0.028316846592 * 86400


def demand_records(forecasts):
    rows = [line.rstrip().split("\t") for line in RAW.read_text().splitlines() if line.startswith("USGS\t")]
    data = pd.DataFrame(rows, columns=["agency","site","date","cfs","status"])
    flows = data.pivot(index="date", columns="site", values="cfs").astype(float)
    status = data.pivot(index="date", columns="site", values="status")
    table = pd.DataFrame(index=pd.Index(forecasts.date, name="date"))
    table["unadjusted_cfs"] = flows["01646500"]
    table["adjusted_cfs"] = flows["01646502"]
    table["unadjusted_status"] = status["01646500"]
    table["adjusted_status"] = status["01646502"]
    table["diversion_m3_day"] = (table.adjusted_cfs - table.unadjusted_cfs) * CFS_TO_M3_DAY
    approved = {"A", "A:R"}
    table["quality"] = np.select([
        table.diversion_m3_day.isna(),
        ~table.adjusted_status.isin(approved) | ~table.unadjusted_status.isin(approved),
        table.diversion_m3_day.le(0)],
        ["missing","estimated_or_provisional","nonpositive_difference"], default="included")
    return table.reset_index()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    forecasts = pd.read_csv("results/baseline_seed42/test_predictions.csv")
    records = demand_records(forecasts)
    records.to_csv(OUT / "diversion_by_date.csv", index=False, float_format="%.3f")
    f = forecasts.merge(records[records.quality == "included"], on="date", validate="one_to_one")
    demand = f.diversion_m3_day.to_numpy()
    summaries, daily = [], []
    for scenario, schedule in [("reported_diversion", demand[:, None]),
                               ("constant_at_matched_mean", [demand.mean()]),
                               ("original_3_million", [3e6])]:
        results, _ = replay(f, demand_m3=schedule, environmental_flow_cms=20., diversion_fraction=.1)
        results["scenario"] = scenario
        daily.append(results)
        months = pd.to_datetime(results.date).dt.month
        seasons = months.map({12:"DJF",1:"DJF",2:"DJF",3:"MAM",4:"MAM",5:"MAM",
                              6:"JJA",7:"JJA",8:"JJA",9:"SON",10:"SON",11:"SON"})
        for period, group in [("all",results), *results.groupby(seasons)]:
            average = group.groupby("policy")[["overcommitment_m3","unmet_demand_m3"]].mean()
            days = group.date.nunique()
            avoided = average.at["bma_mean","overcommitment_m3"] - average.at["bma_lower_5pct","overcommitment_m3"]
            extra = average.at["bma_lower_5pct","unmet_demand_m3"] - average.at["bma_mean","unmet_demand_m3"]
            over = group.overcommitment_m3.gt(1e-6).groupby(group.policy).mean()
            summaries.append(dict(scenario=scenario, period=period, days=days,
                avoided_excess_m3_day=avoided, extra_unmet_m3_day=extra,
                break_even_ratio=extra/avoided if avoided > 0 else np.nan,
                mean_policy_overcommit_fraction=over["bma_mean"],
                low_policy_overcommit_fraction=over["bma_lower_5pct"]))
    pd.concat(daily).to_csv(OUT / "decisions.csv.gz", index=False, float_format="%.3f",
                             compression={"method":"gzip","mtime":0})
    pd.DataFrame(summaries).to_csv(OUT / "policy_comparison.csv", index=False, float_format="%.5f")


if __name__ == "__main__":
    main()
