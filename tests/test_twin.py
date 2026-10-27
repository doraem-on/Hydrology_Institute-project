import numpy as np
import pandas as pd
import pytest

from hydrology.decision_replay import replay
from hydrology.twin import allocate_water, available_observations, bucket_step, demand_scenarios, plan_from_observations


def test_observation_availability_not_just_acquisition_date():
    observations = pd.DataFrame([
        ['u', 'wetness', '2024-01-01', '2024-01-03', .3, 'a'],
        ['u', 'wetness', '2024-01-04', '2024-01-10', .9, 'b'],
        ['u', 'wetness', '2024-01-01', '2024-02-01', .8, 'revised'],
    ], columns=['unit_id', 'variable', 'observed_at', 'available_at', 'value', 'source_id'])
    result = available_observations(observations, '2024-01-05')
    assert result.value.tolist() == [.3]
    assert result.source_id.tolist() == ['a']
    assert available_observations(observations, '2024-01-05', max_age_days=1).empty
    observations.loc[1, 'available_at'] = '2024-01-02'
    with pytest.raises(ValueError):
        available_observations(observations, '2024-01-05')


def test_demand_units_crop_and_moisture_ablation():
    full = demand_scenarios([10], [1], [.5], dry_rice_mm=10, dry_other_mm=5,
                           wetness_response=.5, efficiency=.5)
    assert full[0] == 1500
    dry = demand_scenarios([10], [1], [0], dry_rice_mm=10, dry_other_mm=5,
                          wetness_response=.5, efficiency=.5)
    assert dry[0] == 2000
    with pytest.raises(ValueError):
        demand_scenarios([10], [1], [np.nan], dry_rice_mm=10, dry_other_mm=5, wetness_response=.5, efficiency=.5)


def test_allocation_supply_budget_environmental_reserve_and_fair_shortage():
    result = allocate_water([10, 20, 30], [500., 1500.], environmental_flow_cms=5,
                            diversion_fraction=.5, period_seconds=100, risk_quantile=0)
    np.testing.assert_allclose(result['allocation_m3'], [62.5, 187.5])
    assert result['allocation_m3'].sum() <= result['supply_budget_m3']
    empty = allocate_water([1], [10., 20.], environmental_flow_cms=5, diversion_fraction=.5)
    assert empty['allocation_m3'].sum() == 0
    zero = allocate_water([10], [0., 0.], environmental_flow_cms=5, diversion_fraction=.5)
    assert zero['allocation_m3'].sum() == 0


def test_bucket_conserves_mass_and_does_not_create_et_water():
    rng = np.random.default_rng(3)
    result = bucket_step(rng.uniform(0, 100, 1000), rng.uniform(0, 80, 1000),
                         rng.uniform(0, 20, 1000), rng.uniform(0, 30, 1000), capacity_mm=100)
    np.testing.assert_allclose(result['mass_balance_residual_mm'], 0, atol=1e-12)
    assert np.all((result['storage_mm'] >= 0) & (result['storage_mm'] <= 100))
    assert bucket_step(0, 0, 0, 5, capacity_mm=100)['actual_et_mm'] == 0


def test_replay_uses_observation_only_for_scoring_and_exposes_tradeoff():
    frame = pd.DataFrame({'date': ['2024-01-01', '2024-01-02'], 'observed_cms': [10, 20],
        'persistence_cms': [20, 10], 'bma_mean_cms': [15, 15], 'bma_lower90_cms': [8, 8]})
    options = dict(demand_m3=[1e6], environmental_flow_cms=0, diversion_fraction=1)
    daily, scores = replay(frame, **options)
    changed = frame.copy()
    changed['observed_cms'] = [1, 1]
    other, _ = replay(changed, **options)
    np.testing.assert_allclose(daily.planned_m3, other.planned_m3)
    score = {s['policy']: s for s in scores}
    assert score['bma_lower_5pct']['overcommitment_day_fraction'] == 0
    assert score['bma_lower_5pct']['mean_unmet_demand_m3'] > score['bma_mean']['mean_unmet_demand_m3']


def test_connected_plan_uses_available_satellite_state_and_abstains_when_stale():
    records = pd.DataFrame([
        ['a', 'rice_fraction', '2024-01-01', '2024-01-02', .8, 'test_crop'],
        ['a', 'surface_wetness', '2024-01-01', '2024-01-02', .4, 'test_totram'],
        ['a', 'flood_fraction', '2024-01-01', '2024-01-02', .1, 'test_flood'],
    ], columns=['unit_id', 'variable', 'observed_at', 'available_at', 'value', 'source_id'])
    units = pd.DataFrame({'unit_id': ['a'], 'area_ha': [100.]})
    options = dict(environmental_flow_cms=5, diversion_fraction=.1, dry_rice_mm=10,
                   dry_other_mm=5, wetness_response=.5, efficiency=.5)
    result = plan_from_observations(records, '2024-01-03', units, [10, 15, 20], **options)
    assert np.isclose(result['demand_m3'][0], 14400)
    assert result['allocation']['allocation_m3'][0] <= result['allocation']['supply_budget_m3']
    assert len(result['review_flags']) == 1
    assert len(result['observation_provenance']) == 3
    stale = plan_from_observations(records, '2024-03-01', units, [10, 15, 20], **options)
    assert stale['status'] == 'insufficient_observations' and stale['allocation'] is None
