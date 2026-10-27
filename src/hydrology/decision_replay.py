"""Replay saved flow forecasts under explicit hypothetical allocation rules.

Real archived flow observations/forecasts, synthetic demand and policy. This is
an exploratory decision stress test, NOT evidence of satellite benefit or a
validated Potomac abstraction policy. No model is refit on the test period.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.twin import allocate_water


def replay(frame, *, demand_m3, environmental_flow_cms, diversion_fraction):
    columns = ['observed_cms', 'persistence_cms', 'bma_mean_cms', 'bma_lower90_cms']
    if not {'date', *columns} <= set(frame):
        raise ValueError('Missing saved forecast columns')
    dates = pd.to_datetime(frame.date)
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError('Forecast dates must be unique and increasing')
    values = frame[columns].to_numpy(float)
    if not len(frame) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Invalid forecast/observation values')
    observed_budget = np.maximum(frame.observed_cms.to_numpy()-environmental_flow_cms, 0)*86400*diversion_fraction
    rows = []
    for policy, col in [('persistence', 'persistence_cms'), ('bma_mean', 'bma_mean_cms'),
                        ('bma_lower_5pct', 'bma_lower90_cms')]:
        for index, row in enumerate(frame.itertuples(index=False)):
            result = allocate_water([getattr(row, col)], demand_m3,
                environmental_flow_cms=environmental_flow_cms, diversion_fraction=diversion_fraction)
            planned = float(result['allocation_m3'].sum())
            feasible = min(planned, observed_budget[index])
            oracle = min(float(np.sum(demand_m3)), observed_budget[index])
            rows.append({'date': str(row.date), 'policy': policy,
                'planned_m3': planned, 'feasible_delivery_m3': feasible,
                'overcommitment_m3': max(planned-observed_budget[index], 0),
                'unmet_demand_m3': float(np.sum(demand_m3))-feasible,
                'foregone_feasible_delivery_m3': oracle-feasible})
    result = pd.DataFrame(rows)
    summary = []
    for policy, group in result.groupby('policy'):
        summary.append({'policy': policy, 'days': len(group),
            'overcommitment_day_fraction': float((group.overcommitment_m3 > 1e-6).mean()),
            'mean_overcommitment_m3': float(group.overcommitment_m3.mean()),
            'mean_unmet_demand_m3': float(group.unmet_demand_m3.mean()),
            'mean_foregone_feasible_delivery_m3': float(group.foregone_feasible_delivery_m3.mean())})
    return result, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--forecasts', type=Path, default=Path('results/baseline_seed42/test_predictions.csv'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--demand-m3', type=float, nargs='+', default=[1e6, 1e6, 1e6])
    parser.add_argument('--environmental-flow-cms', type=float, default=20.)
    parser.add_argument('--diversion-fraction', type=float, default=0.1)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Choose a new output directory')
    daily, summary = replay(pd.read_csv(args.forecasts), demand_m3=args.demand_m3,
        environmental_flow_cms=args.environmental_flow_cms, diversion_fraction=args.diversion_fraction)
    report = {'status': 'exploratory_scenario_not_field_validation',
        'input_sha256': hashlib.sha256(args.forecasts.read_bytes()).hexdigest(),
        'source': str(args.forecasts), 'demand_m3_per_day': args.demand_m3,
        'environmental_flow_cms': args.environmental_flow_cms, 'diversion_fraction': args.diversion_fraction,
        'policy_parameters': 'Hypothetical, not basin-calibrated or legally prescribed',
        'satellite_inputs_used': False, 'results': summary,
        'interpretation': 'Lower-tail planning trades delivery for fewer supply overcommitments; no universal winner implied.'}
    args.output.mkdir(parents=True)
    daily.to_csv(args.output/'daily_decisions.csv', index=False)
    (args.output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    for item in summary:
        ax.scatter(item['mean_unmet_demand_m3']/1e6, item['overcommitment_day_fraction']*100, s=60)
        ax.annotate(item['policy'], (item['mean_unmet_demand_m3']/1e6, item['overcommitment_day_fraction']*100),
                    xytext=(6, 6), textcoords='offset points')
    ax.set(xlabel='Mean unmet hypothetical demand (million m³/day)',
           ylabel='Days with supply overcommitment (%)',
           title='Potomac forecast replay: hypothetical allocation scenario')
    ax.margins(0.25)
    fig.text(.5, .02, 'Archived flow forecasts; synthetic demand/policy. No satellite validation.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(args.output/'decision_tradeoff.png', dpi=180)
    plt.close(fig)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
