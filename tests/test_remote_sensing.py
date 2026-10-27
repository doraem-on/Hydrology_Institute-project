import numpy as np
import pandas as pd
import pytest

from hydrology.remote_sensing import (Trapezoid, fit_rice_classifier, fit_trapezoid,
    flood_candidates, landslide_candidates, modis_quality, ndti, rice_features)
from hydrology.satellite_pipeline import classify_rice, fit_moisture


def scene():
    vi = np.tile(np.linspace(0.05, 0.95, 100), 40)
    wetness = np.repeat(np.linspace(0, 1, 40), 100)
    temperature = (315-10*vi)*(1-wetness)+(290-2*vi)*wetness
    return vi, temperature


def test_trapezoid_physical_endpoints_and_invalid_domain():
    model = Trapezoid(290, -2, 315, -10, 0, 1, 1000, 10)
    result = model.moisture_index([.5, .5, .5, .5, 1.2, np.nan], [289, 310, 299.5, 280, 300, 300])
    np.testing.assert_allclose(result['moisture_index'][:4], [1, 0, .5, 1])
    assert result['outside_edges'][3]
    assert np.isnan(result['moisture_index'][4:]).all()


def test_scene_fit_recovers_wetness_gradient():
    vi, temp = scene()
    model = fit_trapezoid(vi, temp)
    result = model.moisture_index(np.array([.5, .5]), np.array([290, 309]))
    assert result['moisture_index'][0] > .9
    assert result['moisture_index'][1] < .1
    assert model.fitted_pixels == 4000


@pytest.mark.parametrize('vi,temp', [(np.ones(100), np.ones(100)*300), (np.arange(5)/5, np.ones(5)*300)])
def test_scene_fit_rejects_unidentifiable_edges(vi, temp):
    with pytest.raises(ValueError):
        fit_trapezoid(vi, temp)


def test_modis_qc_scaling_and_cloud_rejection():
    vi, temp = modis_quality([5000]*5, [0, 1, 0, 0, 0], [15000]*5, [0, 0, 2, 64, np.nan])
    assert vi[0] == .5 and temp[0] == 300
    assert np.isnan(vi[1:]).all() and np.isnan(temp[1:]).all()


def test_turbidity_is_masked_and_invalid_ratio_is_nan():
    result = ndti([.3, .3, 0, -.1], [.1, .1, 0, .1], [1, 0, 1, 1])
    assert np.isclose(result[0], .5)
    assert np.isnan(result[1:]).all()


def test_flood_is_db_drop_with_water_slope_and_component_masks():
    before = np.full((8, 8), -10.)
    after = before.copy()
    after[1:4, 1:4] = -20
    after[6, 6] = -20
    slope, permanent, valid = np.zeros((8, 8)), np.zeros((8, 8)), np.ones((8, 8))
    permanent[1, 1] = 1
    valid[7, 7] = 0
    result = flood_candidates(before, after, slope, permanent, valid)
    assert np.nansum(result) == 8
    assert result[6, 6] == 0 and result[1, 1] == 0 and np.isnan(result[7, 7])
    slope[:] = 20
    assert np.nansum(flood_candidates(before, after, slope, permanent, valid)) == 0


def test_landslide_screen_is_bidirectional_and_requires_slope():
    before, after = np.full((4, 4), -15.), np.full((4, 4), -10.)
    result = landslide_candidates(before, after, np.full((4, 4), 20), np.ones((4, 4)))
    assert result.sum() == 16
    assert landslide_candidates(before, after, np.zeros((4, 4)), np.ones((4, 4))).sum() == 0


def test_rice_log_ratio_and_group_leakage():
    vv, vh = np.array([[-10., -9, -8]]), np.array([[-20., -19, -18]])
    x = rice_features(vv, vh, [0, 12, 24])
    np.testing.assert_allclose(x[0, 6:9], 10)
    with pytest.raises(ValueError, match='Spatial leakage'):
        fit_rice_classifier(np.tile(x, (4, 1)), [0, 1, 0, 1], ['a', 'a', 'b', 'b'],
                            np.tile(x, (2, 1)), [0, 1], ['a', 'c'])
    with pytest.raises(ValueError):
        rice_features(vv, vh, [0, 24, 12])


def test_rice_holdout_smoke_not_accuracy_evidence():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(80, 8))
    y = np.tile([0, 1], 40)
    x[:, 0] += y*2
    x[::7, 2] = np.nan
    _, probability, scores = fit_rice_classifier(x[:60], y[:60], np.arange(60), x[60:], y[60:], np.arange(60, 80))
    assert np.all((probability >= 0) & (probability <= 1))
    assert 0 <= scores['brier_score'] <= 1
    assert np.sum(scores['confusion_matrix_true_rows_0_1']) == 20


def test_moisture_pipeline_retains_rejected_scene_rows():
    vi, temp = scene()
    frame = pd.DataFrame({'scene_id': 's', 'ndvi': vi, 'lst_kelvin': temp, 'elevation': 100, 'observed_end': '2024-07-01'})
    result, models = fit_moisture(frame)
    assert models[0]['status'] == 'fitted' and result.moisture_index.notna().sum() > 3000
    rejected, models = fit_moisture(frame.iloc[:10])
    assert models[0]['status'] == 'rejected' and rejected.moisture_index.isna().all()


def test_rice_export_pipeline_and_field_consistency():
    rows = []
    for i in range(24):
        for month in range(6, 10):
            rows.append({'field_id': f'f{i:02}', 'block_id': f'b{i}', 'rice': i % 2,
                'split': 'train' if i < 16 else 'test', 'observed_start': f'2024-{month:02}-01',
                'observed_end': f'2024-{month+1:02}-01', 'VV': -10+i%2, 'VH': -20+(i%2)*month,
                'label_source': 'synthetic_unit_test', 'label_available_at': '2025-01-01'})
    frame = pd.DataFrame(rows)
    result, scores = classify_rice(frame)
    assert len(result) == 8 and 'retrospective' in scores['mode']
    frame.loc[0, 'rice'] = 1
    with pytest.raises(ValueError, match='metadata changes'):
        classify_rice(frame)
