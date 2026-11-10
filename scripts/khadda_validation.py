"""Evaluate the same 2023 fit in all later monsoons; score usable preparation time."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from khadda_multiseason import OUT, audit, run


def summarize(events, score, design):
    events = events.loc[events.level == "warning"].copy()
    score = score.loc[score.level == "warning"].copy()
    rows = []
    for season in ["all", "2024", "2025", "2026"]:
        times = events if season == "all" else events[events["sample"] == season]
        metrics = score if season == "all" else score[score["sample"] == season]
        by_model = times.pivot(index="crossing_ist", columns="policy", values="lead_hours")
        paired = (by_model.upstream - by_model.local).dropna()
        for model in ["local", "upstream"]:
            lead = by_model[model]
            model_scores = metrics[metrics.policy == model]
            rows.append(dict(design=design, season=season, model=model, crossings=len(lead),
                warned=lead.count(), six_hours_or_more=lead.ge(6).sum(),
                twelve_hours_or_more=lead.ge(12).sum(), matched_eligible_hours=model_scores.matched_below_hours.sum(),
                false_alert_hours=model_scores.false_alert_hours.sum(), both_warned=len(paired),
                median_paired_gain_h=paired.median() if len(paired) else None))
    return pd.DataFrame(rows)


def plot_checks(checks):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), layout="constrained")
    colors = {"local": "#8ca3b1", "upstream": "#116a70"}
    labels = {"local": "Khadda only", "upstream": "Khadda + Triveni"}
    annual = checks[(checks.design == "annual") & (checks.season != "all")]
    total = checks[checks.season == "all"]
    for index, model in enumerate(colors):
        season = annual[annual.model == model]
        pos = np.arange(len(season)) + (index - 0.5) * 0.32
        ax = axes[0]
        bars = ax.barh(pos, season.six_hours_or_more / season.crossings, height=.3,
                       color=colors[model], label=labels[model])
        ax.bar_label(bars, labels=[f"{a}/{b}" for a,b in zip(season.six_hours_or_more,season.crossings)],
                     padding=3, fontsize=9)
        policy = total[total.model == model]
        bars = axes[1].barh(np.arange(len(policy)) + (index - .5)*.32,
                            policy.false_alert_hours, height=.3, color=colors[model])
        axes[1].bar_label(bars, padding=3, fontsize=9)
    axes[0].set(yticks=[0,1,2], yticklabels=["2024","2025","2026"], xlim=(0,1.08),
                xticks=[0,.25,.5,.75,1], xticklabels=["0","25","50","75","100"],
                xlabel="Share of crossings (%)", title="At least six hours of warning")
    axes[1].set(yticks=[0,1], yticklabels=["Updated yearly","Fixed after 2023"],
                xlim=(0,152), xlabel="False alert hours", title="False alarms across three monsoons")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center",
               ncols=2, frameon=False, fontsize=9)
    for ax in axes:
        ax.invert_yaxis()
        ax.spines[["top","right"]].set_visible(False)
    fig.savefig(OUT / "preparation_time.png", dpi=190)
    plt.close(fig)


def verify_bulletins(observed):
    excerpts = pd.read_csv(OUT / "bihar_2025_excerpts.csv", parse_dates=["official_issue_ist", "valid_ist"])
    excerpts["issue"] = excerpts.official_issue_ist.dt.floor("h")
    excerpts["lead"] = (excerpts.valid_ist - excerpts.issue) / pd.Timedelta(hours=1)
    issued = pd.read_csv(OUT / "stage_forecasts.csv.gz", parse_dates=["issue"],
                         usecols=["issue","lead","local","upstream"])
    pairs = excerpts.merge(issued, on=["issue","lead"], how="left", validate="one_to_one")
    pairs["observed_m"] = observed.reindex(pairs.valid_ist).to_numpy()
    if not pairs.lead.between(1, 24).all() or pairs[["observed_m", "local", "upstream", "official_m"]].isna().any().any():
        raise ValueError("Official comparisons require complete forecasts and observations at a common target time")
    pairs.to_csv(OUT / "bihar_2025_verification.csv", index=False, float_format="%.5f")


def main():
    stage = pd.read_csv(OUT / "source_stage.csv.gz", index_col="time_ist", parse_dates=True).asfreq("h")
    verify_bulletins(stage.khadda_m)
    # This single call fits each lead once, strictly before June 2024.
    fixed = run(stage, pd.Timestamp("2024-06-01"), stage.index.max())
    scores, events = [], []
    for year, f in fixed.groupby(fixed.issue.dt.year):
        observations = stage.khadda_m.loc[f"{year}-06-01":f"{year}-10-31 23:00"]
        s, e = audit(f, observations, ["local", "upstream"], str(year))
        scores.append(s)
        events.append(e)
    fixed_events = pd.concat(events)
    fixed_scores = pd.concat(scores)
    fixed_events.to_csv(OUT / "fixed_fit_events.csv", index=False)
    fixed_scores.to_csv(OUT / "fixed_fit_scores.csv", index=False)
    original = pd.read_csv(OUT / "event_timings.csv")
    original_scores = pd.read_csv(OUT / "warning_scores.csv")
    original = original[original["sample"].isin(["2024","2025","2026"])]
    original_scores = original_scores[original_scores["sample"].isin(["2024","2025","2026"])]
    checks = pd.concat([summarize(original, original_scores, "annual"),
                        summarize(fixed_events, fixed_scores, "fixed_2023")])
    plot_checks(checks)
    checks.to_csv(OUT / "preparation_time.csv", index=False, float_format="%.2f")


if __name__ == "__main__":
    main()
