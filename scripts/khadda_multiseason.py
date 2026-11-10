"""Chronological hourly forecasts of Khadda stage, verified across monsoons."""
from pathlib import Path
import numpy as np
import pandas as pd
from hydrology.gandak_warning import rain_matrix, rain_features
from hydrology.town_warning_replay import verify

OUT = Path("results/khadda_multiseason")
HOUR = pd.Timedelta(hours=1)
LEVELS = {"warning": 95., "danger": 96.}


def features(s):
    x = pd.DataFrame({s.name: s})
    for h in (1, 3, 6, 12, 24):
        x[f"{s.name}_change_{h}"] = s - s.shift(h)
    return x.where(s.rolling(25).count().eq(25), axis=0)


def fit_ridge(x, y, train):
    # Model the change in metres. Use unit ridge penalty on standardized inputs.
    a, b = x.loc[train], y.loc[train]
    mean, std = a.mean(), a.std().replace(0, 1.)
    z = ((a - mean) / std).to_numpy()
    weights = np.linalg.solve(z.T @ z + np.eye(z.shape[1]), z.T @ (b - b.mean()))
    return mean, std, weights, b.mean()


def predict(fit, x):
    mean, std, weights, intercept = fit
    return intercept + ((x - mean) / std).to_numpy() @ weights


def run(stages, start, end, weather=None):
    town = stages.khadda_m
    # Conservative one-hour delay for both gauges. The archive lacks issue vintages.
    local = features(town.shift(1))
    upstream = features(stages.triveni_m.shift(1))
    combined = local.join(upstream)
    clock = town.index.tz_localize("Asia/Kolkata").tz_convert("UTC")
    # Six-hour scheduled outages or frozen readings every seventh monsoon day.
    # Dates are fixed independently of river level and the occurrence of a flood.
    up_latest = stages.triveni_m.shift(1)
    day_no = (town.index.dayofyear - pd.to_datetime(town.index.year.astype(str) + "-06-01").dayofyear)
    fault = (day_no % 7 == 0) & (town.index.hour < 6)
    dropped = up_latest.mask(fault)
    held = up_latest.where(~fault, dropped.ffill(limit=6))
    broken = {"outage_fallback": local.join(features(dropped)), "frozen_sensor": local.join(features(held))}
    traces = []
    for lead in range(1, 25):
        models = {"local": local, "upstream": combined}
        complete = combined
        if weather is not None:
            rain = rain_features(weather, clock, lead, 12).set_axis(town.index)
            complete = combined.join(rain)
            models["upstream_rain"] = complete
        delta = town.shift(-lead) - local.khadda_m
        usable = complete.notna().all(axis=1)
        train = usable & delta.notna() & (town.index + lead*HOUR < start)
        test = usable & (town.index >= start) & (town.index <= end)
        frame = pd.DataFrame({"issue": town.index[test], "lead": lead, "training_pairs": train.sum()})
        fitted = {name: fit_ridge(x, delta, train) for name, x in models.items()}
        for name, x in models.items():
            frame[name] = local.khadda_m[test].to_numpy() + predict(fitted[name], x.loc[test])
        if weather is None:
            for name, inputs in broken.items():
                available = test & inputs.notna().all(axis=1)
                issued = pd.Series(frame.local.to_numpy(), index=local.index[test])
                issued.loc[available] = local.khadda_m[available] + predict(fitted["upstream"], inputs.loc[available])
                frame[name] = issued.to_numpy()
        traces.append(frame)
    return pd.concat(traces, ignore_index=True)


def audit(f, stage, models, tag):
    g = f.groupby("issue")
    peaks = g[models].max().where(g.size().eq(24), axis=0)
    summaries, event_rows = [], []
    future_values = pd.concat([stage.shift(-h) for h in range(1, 25)], axis=1)
    for label, limit in LEVELS.items():
        signals = peaks.ge(limit).astype("boolean").where(peaks.notna()).reindex(stage.index)
        summaries1, events = verify(signals, stage, {label:limit}, models)
        opportunities = (stage < limit) & future_values.notna().all(axis=1)
        valid = opportunities.reindex(signals.index) & signals.notna().all(axis=1)
        future = future_values.max(axis=1)
        for method in models:
            false = signals.index[valid & signals[method].fillna(False) & future.reindex(signals.index).lt(limit)]
            summaries1.loc[summaries1.policy==method,"false_alert_runs"] = false.to_series().diff().ne(HOUR).sum()
        summaries.append(summaries1.assign(sample=tag))
        event_rows.append(events.assign(sample=tag))
    return pd.concat(summaries), pd.concat(event_rows)


def main():
    stages = pd.read_csv(OUT/"source_stage.csv.gz", index_col="time_ist", parse_dates=True).asfreq("h")
    if stages.index.has_duplicates or (stages.dropna() < 0).any().any():
        raise ValueError("Unexpected gauge records")
    tables, audits, events = [], [], []
    for year in (2024,2025,2026):
        start = pd.Timestamp(year,6,1)
        end = min(pd.Timestamp(year,10,31,23), stages.index.max())
        f = run(stages, start, end)
        # Start the verification clock at season start, including initial missing inputs.
        a,e = audit(f, stages.khadda_m.loc[start:end], ["local","upstream","outage_fallback","frozen_sensor"], str(year))
        tables.append(f)
        audits.append(a)
        events.append(e)
    f = pd.concat(tables)
    f.to_csv(OUT/"stage_forecasts.csv.gz",index=False,float_format="%.5f",compression={"method":"gzip","mtime":0})
    # Separate common-data experiment: archived rainfall starts in late July 2026.
    rain = rain_matrix(Path("data/raw/gandak_inputs/rain.csv"))
    start = pd.Timestamp("2026-09-16")
    wf = run(stages.loc["2026-07-30":], start, stages.index.max(), rain)
    a,e = audit(wf, stages.khadda_m.loc[start:], ["local","upstream","upstream_rain"], "rain_2026")
    audits.append(a)
    events.append(e)
    pd.concat(audits).to_csv(OUT/"warning_scores.csv",index=False)
    timings = pd.concat(events)
    timings.to_csv(OUT/"event_timings.csv",index=False)
    joint = (timings.loc[timings["sample"] != "rain_2026"]
             .pivot(index=["level", "crossing_ist"], columns="policy", values="lead_hours"))
    joint["upstream_minus_local_hours"] = joint.upstream - joint.local
    joint.to_csv(OUT/"paired_leads.csv")
    wf.to_csv(OUT/"rain_forecasts.csv.gz",index=False,float_format="%.5f",
              compression={"method":"gzip","mtime":0})

    # All observed onsets including any before forecasts become available.
    before = stages.khadda_m.shift().rolling(24).max()
    catalog = [stages.index[(stages.khadda_m >= v) & (before < v)].to_frame(index=False,name="crossing_ist").assign(level=k)
               for k,v in LEVELS.items()]
    pd.concat(catalog).sort_values("crossing_ist").to_csv(OUT/"crossings.csv",index=False)
    official = pd.read_csv(OUT/"official_bulletins.csv",parse_dates=["issue_ist","valid_ist"])
    if not (official.valid_ist-official.issue_ist == 24*HOUR).all() or official.issue_ist.duplicated().any():
        raise ValueError("Expected distinct next-day official forecasts")
    matched = official.merge(f[f.lead.eq(24)][["issue","local","upstream"]],left_on="issue_ist",right_on="issue",how="left")
    matched["observed_m"] = stages.khadda_m.reindex(matched.valid_ist).to_numpy()
    matched.drop(columns="issue").to_csv(OUT/"official_comparison.csv",index=False,float_format="%.5f")
    rows=[]
    matched=matched.dropna(subset=["observed_m","local","upstream","official_stage_m"])
    for label,level in LEVELS.items():
        high = matched.observed_m >= level
        for method in ["local","upstream","official_stage_m"]:
            signals = matched[method] >= level
            rows.append(dict(level=label,method=method,paired=len(high),observed_high=high.sum(),
                    hits=(signals&high).sum(),misses=(~signals&high).sum(),false_high=(signals&~high).sum(),
                    mae_m=(matched[method]-matched.observed_m).abs().mean()))
    pd.DataFrame(rows).to_csv(OUT/"official_scores.csv",index=False,float_format="%.4f")


if __name__ == "__main__":
    main()
