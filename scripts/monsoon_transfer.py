"""Check hourly transfer coverage and independently test a daily Gandak benchmark."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.gandak_hourly import apply_ridge, fit_ridge, TEST_START
from hydrology.gandak_warning import HOUR, model_inputs, rain_features, warning_audit

OUTPUT = Path("results/monsoon_transfer")
FROZEN = OUTPUT / "frozen_combined.json"


def score_frozen(barrage, inputs, out, original=False):
    """Score exact future observations using saved coefficients. Never refit."""
    model = json.loads(FROZEN.read_text())
    q, base, clock, gauge, rain = model_inputs(inputs, barrage)
    if not original and TEST_START.year in q.index.year:
        raise ValueError("External validation must exclude the development monsoon")
    if not original and q.index.year.nunique() != 1:
        raise ValueError("Supply one independent season at a time")
    start = TEST_START if original else q.index.min()
    forecasts = []
    for key, fit in model["leads"].items():
        lead = int(key)
        weather = rain_features(rain, clock, lead, model["gfs_delay_hours"]).set_axis(q.index)
        x = base.join(gauge).join(weather)
        target = q.shift(-lead)
        ok = x.notna().all(axis=1) & target.notna() & (q.index >= start)
        level = x.loc[ok, "upstream_level"]
        lo, hi = fit["gauge_range_m"]
        forecasts.append(pd.DataFrame(dict(issue_time=q.index[ok], lead_h=lead,
            observed=target[ok].to_numpy(), combined=apply_ridge(fit, x[ok], np.log1p(q[ok])),
            gauge_m=level.to_numpy(), below_training=level.lt(lo).to_numpy(),
            above_training=level.gt(hi).to_numpy())))
    f = pd.concat(forecasts, ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    if f.empty:
        raise ValueError("No matched hourly forecasts can be scored")
    f.to_csv(out / "frozen_forecasts.csv.gz", index=False, float_format="%.5f",
             compression={"method":"gzip", "mtime":0})
    a, e = warning_audit(f, q, model["threshold_m3s"], methods=["combined"], start=start)
    a["missed_assessable_onsets"] = a.assessable_onsets - a.onsets_warned
    a["window_hours"] = int((q.index >= start).sum())
    a["complete_24h_forecast_issues"] = int(f[f.lead_h <= 24].groupby("issue_time").size().eq(24).sum())
    a.to_csv(out / "hourly_alerts.csv", index=False)
    e.reindex(columns=["method", "onset_ist", "eligible_issues", "first_warning_hours"]).to_csv(
        out / "hourly_events.csv", index=False)
    return f


def range_audit(f, out):
    # Peak magnitudes use one complete forward 72-hour trace per issue.
    traces = []
    for issue, g in f.groupby("issue_time"):
        if len(g) != 72:
            continue
        traces.append(dict(issue_time=issue, gauge_m=g.gauge_m.iloc[0],
            range_band=("above" if g.above_training.any() else "below" if g.below_training.any() else "inside"),
            predicted_peak=g.combined.max(), observed_peak=g.observed.max()))
    peaks = pd.DataFrame(traces, columns=["issue_time","gauge_m","range_band","predicted_peak","observed_peak"])
    peaks["peak_error"] = peaks.predicted_peak - peaks.observed_peak
    peaks["absolute_error"] = peaks.peak_error.abs()
    peaks.to_csv(out / "peak_flags.csv", index=False, float_format="%.4f")
    cutoff = peaks.absolute_error.quantile(.90)
    peaks["large"] = peaks.absolute_error >= cutoff
    s = peaks.groupby("range_band").agg(issues=("large","size"), large_errors=("large","sum"),
        mean_absolute_peak_error=("absolute_error","mean"), mean_peak_bias=("peak_error","mean"))
    s["large_error_cut_m3s"] = cutoff
    s.to_csv(out / "peak_flag_summary.csv", float_format="%.3f")


def historical_audit():
    hist = pd.read_csv(OUTPUT / "historical_inflow.csv", parse_dates=["timestamp"]).set_index("timestamp").inflow_m3s
    cover = []
    for year in sorted(set(hist.index.year)):
        clock = pd.date_range(f"{year}-06-01", f"{year}-10-31 23:00", freq="h")
        q = hist.reindex(clock)
        cover.append(dict(monsoon=year, hours=len(q), observed_hours=q.count(),
                          complete_25h_histories=q.rolling(25).count().eq(25).sum()))
    pd.DataFrame(cover).to_csv(OUTPUT / "historic_hourly_coverage.csv", index=False)
    # A separate decision available at the 08:00 reading, using no other input.
    q = hist.asfreq("D")
    z = np.log1p(q)
    x = pd.DataFrame(dict(log_level=z, daily_change=z.diff()))
    y = q.shift(-1)
    ok = x.notna().all(axis=1) & y.notna()
    train, test = ok & (q.index.year == 2024), ok & (q.index.year == 2025)
    limit = q[q.index.year == 2024].quantile(.95)
    fit = fit_ridge(x, z, y, train)
    f = pd.DataFrame(dict(issue_ist=q.index[test], current=q[test].to_numpy(),
        next_morning=y[test].to_numpy(), ridge=apply_ridge(fit,x[test],z[test]),
        persistence=q[test].to_numpy()))
    f.to_csv(OUTPUT / "daily_2025_forecasts.csv", index=False, float_format="%.4f")
    rows = []
    for method in ["ridge","persistence"]:
        below = f.current < limit
        crossing, alert = below & f.next_morning.ge(limit), below & f[method].ge(limit)
        rows.append(dict(method=method, training_pairs=train.sum(), test_pairs=test.sum(),
            training_threshold=limit, eligible_below=below.sum(), crossings=crossing.sum(),
            warned=(alert & crossing).sum(), missed=(~alert & crossing).sum(),
            false_warnings=(alert & ~crossing).sum(), mae=(f[method]-f.next_morning).abs().mean()))
    pd.DataFrame(rows).to_csv(OUTPUT / "daily_transfer_scores.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--external-barrage", type=Path, help="Folder containing source_inflow.csv, hourly IST")
    p.add_argument("--inputs", type=Path, default=Path("data/raw/gandak_inputs"))
    p.add_argument("--output", type=Path, default=OUTPUT)
    args = p.parse_args()
    if args.external_barrage and args.output.resolve() == OUTPUT.resolve():
        p.error("Use a separate --output for an external season")
    forecasts = score_frozen(args.external_barrage or Path("results/gandak_hourly"), args.inputs,
                             args.output, original=args.external_barrage is None)
    range_audit(forecasts, args.output)
    if not args.external_barrage:
        historical_audit()
