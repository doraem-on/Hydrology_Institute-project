"""Compare two fixed tree ensembles with the original ridge on identical hourly issues."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

from hydrology.gandak_hourly import TEST_START, apply_ridge
from hydrology.gandak_warning import HOUR, model_inputs, rain_features, warning_audit
from hydrology.town_warning_replay import september_timing, verify

OUT = Path("results/gandak_model_comparison")
TOWN = Path("results/decision_replay_both")
MODELS = ["ridge", "random_forest", "gradient_boosting", "persistence"]


def compare():
    frozen = json.loads(Path("results/monsoon_transfer/frozen_combined.json").read_text())
    q, base, clock, gauge, rain = model_inputs(Path("data/raw/gandak_inputs"), Path("results/gandak_hourly"))
    log_q = np.log1p(q)
    forest = RandomForestRegressor(n_estimators=150, max_depth=6, min_samples_leaf=10,
                                   random_state=42, n_jobs=1)
    boosting = GradientBoostingRegressor(n_estimators=100, learning_rate=.05, max_depth=2,
                                         min_samples_leaf=10, random_state=42)
    predictions, fits = [], []
    for h in range(1, 25):
        weather = rain_features(rain, clock, h, frozen["gfs_delay_hours"]).set_axis(q.index)
        x = base.join(gauge).join(weather)
        target = q.shift(-h)
        available = x.notna().all(axis=1)
        train = available & target.notna() & (q.index + h * HOUR < TEST_START)
        issue = available & (q.index >= TEST_START)
        table = pd.DataFrame({"issue_time":q.index[issue], "lead_h":h, "observed":target[issue].to_numpy(),
                              "persistence":q[issue].to_numpy()})
        table["ridge"] = apply_ridge(frozen["leads"][str(h)], x[issue], log_q[issue])
        change = np.log1p(target[train]) - log_q[train]
        for name, model in [("random_forest",forest), ("gradient_boosting",boosting)]:
            model.fit(x[train], change)
            table[name] = np.maximum(0., np.expm1(log_q[issue].to_numpy() + model.predict(x[issue])))
        predictions.append(table)
        fits.append(dict(lead_h=h, training_rows=int(train.sum()), issued_rows=int(issue.sum())))
    f = pd.concat(predictions, ignore_index=True)
    if not np.isfinite(f[MODELS]).all().all():
        raise ValueError("Nonfinite model prediction")
    limit = frozen["threshold_m3s"]
    scored = f.dropna(subset=["observed"])
    # All methods have one row per issue/lead. This preserves the established
    # barrage audit, which scores only complete 24-hour verification windows.
    audit, events = warning_audit(scored, q, limit, methods=MODELS)
    events["first_signal_ist"] = events.onset_ist - pd.to_timedelta(events.first_warning_hours, unit="h")
    event_errors = scored[scored.lead_h.eq(24)]
    audit["mae_24h_m3s"] = audit.method.map(event_errors[MODELS].sub(event_errors.observed, axis=0).abs().mean())

    grouped = f.groupby("issue_time")
    peaks = grouped[MODELS].max().where(grouped.size().eq(24), axis=0)
    signals = peaks.ge(limit).astype("boolean").where(peaks.notna())
    stage = pd.read_csv(TOWN / "khadda_stage.csv", parse_dates=["time_ist"]).set_index("time_ist").level_m
    station = pd.read_csv(TOWN / "khadda_station.csv").iloc[0]
    limits = {"warning":station.warning_level, "danger":station.danger_level}
    signals = signals.reindex(q.index[q.index >= TEST_START])
    town_audit, town_onsets = verify(signals, stage, limits, MODELS)
    timing = september_timing(signals, stage, limits, MODELS)
    OUT.mkdir(exist_ok=True, parents=True)
    for name, frame in [("barrage_audit", audit), ("barrage_onsets", events), ("khadda_timing", timing),
                        ("khadda_audit", town_audit), ("khadda_onsets", town_onsets), ("sample_sizes", pd.DataFrame(fits))]:
        frame.to_csv(OUT / f"{name}.csv", index=False, float_format="%.5f")
    f.to_csv(OUT / "forecasts.csv.gz", index=False, float_format="%.5f",
             compression={"method":"gzip", "mtime":0})
    settings = dict(sklearn_version=sklearn.__version__, random_forest=forest.get_params(),
                    gradient_boosting=boosting.get_params(), threshold_m3s=limit,
                    training_target_cutoff_ist=str(TEST_START), rain_cycle_minimum_age_hours=frozen["gfs_delay_hours"])
    (OUT / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    compare()
