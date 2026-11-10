"""Paired verification of the upstream gauge and issued rainfall forecasts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.gandak_hourly import EVENT_ISSUE, TEST_START, barrage_features, predict_ridge, fit_ridge, apply_ridge

METHODS = ["persistence", "barrage", "gauge", "rain", "combined"]
HOUR = pd.Timedelta(hours=1)


def gauge_at_issue(records, issue_utc):
    rows = records.copy()
    for column in ("observed", "available"):
        rows[column] = pd.to_datetime(rows[column], utc=True, format="mixed")
    rows = rows.dropna().sort_values(["available", "observed"])
    if (rows.available < rows.observed).any():
        raise ValueError("A reading cannot be available before it is measured")
    # A late backfill must not replace a newer observation already received.
    rows = rows.loc[rows.observed.eq(rows.observed.cummax())]
    last = pd.merge_asof(pd.DataFrame({"issue": issue_utc}), rows,
                         left_on="issue", right_on="available", direction="backward")
    age = last.issue - last.observed
    return pd.Series(last.level_m.where(age <= 2 * HOUR).to_numpy(), index=issue_utc)


def rain_features(records, issue_utc, lead, delay):
    # Choose a single 00 UTC cycle for all forecast hours of each issue.
    cycle = (issue_utc - delay * HOUR).floor("D")
    hours = (issue_utc.floor("h") - cycle) / HOUR
    run_index = records.index.get_indexer(cycle)
    values = np.full((len(cycle), 2), np.nan)
    for j, (start, end) in enumerate([(-5, 0), (1, lead)]):
        # Intervals end at integer UTC hours. At half past the hour use only
        # endpoints through the forecast valid time; no fractional interpolation.
        offsets = hours.to_numpy(dtype=int)[:, None] + np.arange(start, end + 1)
        ok = (run_index >= 0) & (offsets.min(axis=1) >= 0) & (offsets.max(axis=1) < records.shape[1])
        values[ok, j] = records.to_numpy()[run_index[ok, None], offsets[ok]].sum(axis=1)
    return pd.DataFrame(values, columns=["rain_previous_6h", "rain_to_target"], index=issue_utc)


def rain_matrix(path):
    frame = pd.read_csv(path)
    frame["run"] = pd.to_datetime(frame.run, utc=True)
    frame["valid"] = pd.to_datetime(frame.valid, utc=True)
    frame["hour"] = (frame.valid - frame.run) / HOUR
    if (frame.mm < 0).any() or frame.duplicated(["run", "hour", "site"]).any():
        raise ValueError("Invalid rainfall forecast packet")
    points = frame.pivot(index=["run", "hour"], columns="site", values="mm")
    if set(points.columns) != {0, 1, 2}:
        raise ValueError("Expected the three configured GFS grid points")
    return points.mean(axis=1, skipna=False).unstack().reindex(columns=range(120))


def warning_audit(predictions, q, threshold, methods=METHODS, start=TEST_START):
    # One alert per eligible hourly decision, and one lead-time score per onset.
    # An onset requires 24 consecutive observed hours strictly below the threshold.
    future = pd.concat([q.shift(-h) for h in range(1, 25)], axis=1)
    actual_high = future.max(axis=1).where(future.notna().all(axis=1)) >= threshold
    onsets = q.index[(q >= threshold) & (q.shift(1).rolling(24).max() < threshold)
                     & (q.index >= start)]
    window = predictions[predictions.lead_h <= 24].groupby("issue_time")
    peaks = window[methods].max()
    eligible = peaks.index[(window.size() == 24) & (q.reindex(peaks.index) < threshold)]
    results, events = [], []
    for method in methods:
        alerts = eligible[peaks.loc[eligible, method] >= threshold]
        false_count = int((~actual_high.loc[alerts]).sum())
        false_times = alerts[~actual_high.loc[alerts].to_numpy()]
        false_episodes = int(false_times.to_series().diff().ne(HOUR).sum())
        leads = []
        for onset in onsets:
            opportunities = eligible[(eligible < onset) & (eligible >= onset - 24 * HOUR)]
            alert = alerts[(alerts < onset) & (alerts >= onset - 24 * HOUR)]
            warning = (onset - alert.min()) / HOUR if len(alert) else np.nan
            events.append(dict(method=method, onset_ist=onset, eligible_issues=len(opportunities),
                               first_warning_hours=warning))
            if len(opportunities):
                leads.append(warning)
        results.append(dict(method=method, threshold_m3s=threshold, eligible_issues=len(eligible),
                            alert_issues=len(alerts), false_alert_issues=false_count,
                            false_alert_runs=false_episodes, observed_onsets=len(onsets), assessable_onsets=len(leads),
                            onsets_warned=int(np.isfinite(leads).sum())))
    return pd.DataFrame(results), pd.DataFrame(events)


def model_inputs(folder, barrage_folder):
    q, base = barrage_features(barrage_folder)
    clock = q.index.tz_localize("Asia/Kolkata").tz_convert("UTC")
    level = gauge_at_issue(pd.read_csv(folder / "gauge.csv"), clock)
    gauge = pd.DataFrame({"upstream_level": level.to_numpy(),
                          "upstream_change_6h": level.diff(6).to_numpy()}, index=q.index)
    rainfall = rain_matrix(folder / "rain.csv")
    return q, base, clock, gauge, rainfall


def evaluate(folder, output, delay=12):
    if not 6 <= delay <= 24:
        raise ValueError("GFS availability lag must be 6 to 24 hours")
    q, base, clock, gauge, rainfall = model_inputs(folder, Path("results/gandak_hourly"))
    frozen = dict(training_target_cutoff_ist=str(TEST_START), gfs_delay_hours=delay,
                  threshold_m3s=q[q.index < TEST_START].quantile(0.95), leads={})
    all_predictions, scores = [], []
    z = np.log1p(q)
    for h in range(1, 73):
        rain = rain_features(rainfall, clock, h, delay).set_axis(q.index)
        extended = base.join(gauge).join(rain)
        target = q.shift(-h)
        usable = extended.notna().all(axis=1) & target.notna()
        train = usable & (q.index + h * HOUR < TEST_START)
        test = usable & (q.index >= TEST_START)
        if train.sum() < 100 or not test.any():
            raise ValueError(f"Insufficient matched cases at {h} hours")
        table = pd.DataFrame({"issue_time": q.index[test], "lead_h": h,
                              "observed": target[test].to_numpy(), "persistence": q[test].to_numpy()})
        for method, features in [("barrage", base), ("gauge", base.join(gauge)),
                                 ("rain", base.join(rain)), ("combined", extended)]:
            if method == "combined":
                model = fit_ridge(features, z, target, train)
                model["gauge_range_m"] = [float(gauge.upstream_level[train].min()),
                                          float(gauge.upstream_level[train].max())]
                frozen["leads"][str(h)] = model
                table[method] = apply_ridge(model, features[test], z[test])
            else:
                table[method] = predict_ridge(features, z, target, train, test)
        for method in METHODS:
            errors = table[method] - table.observed
            scores.append(dict(lead_h=h, method=method, train_pairs=train.sum(), test_pairs=test.sum(),
                               potential_test_pairs=(base.notna().all(axis=1) & target.notna()
                                                     & (q.index >= TEST_START)).sum(),
                               mae=errors.abs().mean(), rmse=np.sqrt((errors ** 2).mean())))
        all_predictions.append(table)
    predictions = pd.concat(all_predictions, ignore_index=True)
    if not np.isfinite(predictions[METHODS]).all().all():
        raise ValueError("Nonfinite forecast")
    threshold = q[q.index < TEST_START].quantile(0.95)
    alerts, events = warning_audit(predictions, q, threshold)
    sensitivities = []
    for quantile in [0.90, 0.95, 0.99]:
        cutoff = q[q.index < TEST_START].quantile(quantile)
        audit, timing = warning_audit(predictions, q, cutoff)
        timings = timing.groupby("method").first_warning_hours.median() if len(timing) else {}
        audit["median_lead_warned_hours"] = audit.method.map(timings)
        audit["training_quantile"] = quantile
        sensitivities.append(audit)
    event = predictions[predictions.issue_time == EVENT_ISSUE].sort_values("lead_h")
    if len(event) != 72:
        raise ValueError("Incomplete September crest forecast")
    peaks = []
    for name in ["observed", *METHODS]:
        peak = event.loc[event[name].idxmax()]
        peaks.append(dict(series=name, maximum_m3s=peak[name], first_hour_of_maximum=peak.lead_h))
    output.mkdir(parents=True, exist_ok=True)
    (output / "frozen_combined.json").write_text(json.dumps(frozen, indent=2) + "\n")
    for name, frame in [("scores", pd.DataFrame(scores)), ("alerts", alerts), ("onsets", events),
                        ("threshold_sensitivity", pd.concat(sensitivities)),
                        ("september_crest", pd.DataFrame(peaks)), ("september_forecast", event)]:
        frame.to_csv(output / f"{name}.csv", index=False, float_format="%.5f")
    predictions.to_csv(output / "forecasts.csv.gz", index=False, float_format="%.5f",
                       compression={"method": "gzip", "mtime": 0})
    meta = dict(gfs_assumed_release_hours=delay, timestamps="Asia/Kolkata in forecast tables",
                inputs={name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                        for name in ["rain.csv", "gauge.csv"]})
    (output / "run.json").write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path("data/raw/gandak_inputs"))
    parser.add_argument("--output", type=Path, default=Path("results/gandak_warning"))
    parser.add_argument("--rain-delay", type=int, default=12)
    args = parser.parse_args()
    evaluate(args.inputs, args.output, args.rain_delay)
