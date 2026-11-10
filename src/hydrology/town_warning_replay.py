"""Time the frozen barrage signal against the two published Khadda gauge levels."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.gandak_hourly import TEST_START, apply_ridge
from hydrology.gandak_warning import model_inputs, rain_features

OUT = Path("results/decision_replay_both")
HOUR = pd.Timedelta(hours=1)


def issue_decisions():
    frozen = json.loads(Path("results/monsoon_transfer/frozen_combined.json").read_text())
    q, base, clock, gauge, rain = model_inputs(Path("data/raw/gandak_inputs"), Path("results/gandak_hourly"))
    estimates = {}
    for h in range(1, 25):
        weather = rain_features(rain, clock, h, frozen["gfs_delay_hours"]).set_axis(q.index)
        x = base.join(gauge).join(weather)
        # A forecast requires current inputs only. Future inflow is never consulted.
        ok = (q.index >= TEST_START) & x.notna().all(axis=1)
        values = apply_ridge(frozen["leads"][str(h)], x[ok], np.log1p(q[ok]))
        estimates[h] = pd.Series(values, index=q.index[ok])
    traces = pd.DataFrame(estimates)
    issues = q[q.index >= TEST_START].rename("barrage_now_m3s").to_frame()
    issues["forecast_24h_peak_m3s"] = traces.max(axis=1, skipna=False)
    limit = frozen["threshold_m3s"]
    for source, policy in [("forecast_24h_peak_m3s","model"), ("barrage_now_m3s","last_reading")]:
        value = issues[source]
        issues[policy] = value.ge(limit).astype("boolean").where(value.notna())
    return issues.rename_axis("issue_ist")


def verify(issues, stage, limits):
    # Work on a true hourly grid. Never bridge a missing reading when dating a crossing.
    stage = stage.sort_index().asfreq("h")
    future = pd.concat([stage.shift(-h) for h in range(1, 25)], axis=1)
    rows, onsets = [], []
    for label, limit in limits.items():
        prior = stage.shift().rolling(24).max()
        events = stage.index[(stage >= limit) & prior.lt(limit) & (stage.index >= issues.index.min())]
        below = stage.reindex(issues.index).lt(limit)
        observed = future.max(axis=1, skipna=False).reindex(issues.index)
        common = below & observed.notna() & issues[["model","last_reading"]].notna().all(axis=1)
        for policy in ["model","last_reading"]:
            alerts = issues.index[common & issues[policy].fillna(False)]
            false = int(observed.reindex(alerts).lt(limit).sum())
            eligible_events, warned = 0, 0
            for event in events:
                before = (issues.index >= event - 24*HOUR) & (issues.index < event)
                chances = issues.index[before & common]
                first = alerts.intersection(chances).min()
                eligible_events += int(len(chances) > 0)
                warned += int(pd.notna(first))
                onsets.append(dict(level=label, policy=policy, crossing_ist=event,
                    eligible_issues=len(chances), first_alert_ist=first, lead_hours=(event-first)/HOUR))
            rows.append(dict(level=label, stage_m=limit, policy=policy, matched_below_hours=common.sum(),
                alert_hours=len(alerts), false_alert_hours=false, observed_onsets=len(events),
                assessable_onsets=eligible_events, warned=warned, missed=eligible_events-warned))
    return pd.DataFrame(rows), pd.DataFrame(onsets)


def september_timing(issues, stage, limits):
    # Dates define the previously studied September event, not the model's issue rule.
    begin, end = pd.Timestamp("2026-09-24"), pd.Timestamp("2026-09-30")
    event = issues.loc[begin:end]
    first_signals = {name: event.index[event[name].fillna(False)].min()
                     for name in ["model","last_reading"]}
    rows = []
    for label, limit in limits.items():
        episode = stage.loc[begin:end]
        first = episode.index[episode.ge(limit)].min()
        if pd.isna(first) or (stage.loc[first-HOUR:first].size != 2
                             or not stage.loc[first-HOUR] < limit):
            raise ValueError(f"Unverified first crossing of {label}")
        for policy, signal in first_signals.items():
            rows.append(dict(level=label, threshold_m=limit, crossing_ist=first,
                policy=policy, first_signal_ist=signal, hours_before_crossing=(first-signal)/HOUR))
    return pd.DataFrame(rows)


def main():
    station = pd.read_csv(OUT / "khadda_station.csv").iloc[0]
    limits = {"warning": station.warning_level, "danger": station.danger_level}
    stage = pd.read_csv(OUT / "khadda_stage.csv", parse_dates=["time_ist"]).set_index("time_ist").level_m
    decisions = issue_decisions()
    audit, events = verify(decisions, stage, limits)
    timing = september_timing(decisions, stage, limits)
    decisions.join(stage).to_csv(OUT / "khadda_hourly_replay.csv", float_format="%.5f")
    audit.to_csv(OUT / "khadda_alert_audit.csv", index=False)
    events.to_csv(OUT / "khadda_onsets.csv", index=False)
    timing.to_csv(OUT / "khadda_september_timing.csv", index=False)


if __name__ == "__main__":
    main()
