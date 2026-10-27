"""Fit satellite baselines from the Earth Engine CSV exports, with provenance."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hydrology.remote_sensing import fit_rice_classifier, fit_trapezoid, rice_features


def fit_moisture(frame):
    required = {'scene_id', 'ndvi', 'lst_kelvin', 'elevation', 'observed_end'}
    if not required <= set(frame):
        raise ValueError(f'Missing columns: {sorted(required-set(frame))}')
    frame = frame.copy()
    frame['moisture_index'] = np.nan
    frame['unclipped_index'] = np.nan
    frame['edge_status'] = 'not_fitted'
    # Fixed elevation stratification is an initial safeguard, not proof of
    # homogeneous meteorology. Evaluate geography/weather strata in the study.
    frame['elevation_stratum'] = np.floor(frame.elevation/200)
    models = []
    for (scene, elevation), group in frame.groupby(['scene_id', 'elevation_stratum']):
        try:
            model = fit_trapezoid(group.ndvi, group.lst_kelvin)
            result = model.moisture_index(group.ndvi, group.lst_kelvin)
            frame.loc[group.index, 'moisture_index'] = result['moisture_index']
            frame.loc[group.index, 'unclipped_index'] = result['unclipped_index']
            frame.loc[group.index, 'edge_status'] = np.where(result['valid'], 'fitted', 'outside_ndvi_domain')
            models.append({'scene_id': str(scene), 'elevation_stratum': float(elevation),
                           'status': 'fitted', **asdict(model)})
        except ValueError as error:
            frame.loc[group.index, 'edge_status'] = 'insufficient_scene_support'
            models.append({'scene_id': str(scene), 'elevation_stratum': float(elevation),
                           'status': 'rejected', 'reason': str(error)})
    return frame, models


def classify_rice(frame):
    required = {'field_id', 'block_id', 'rice', 'split', 'observed_start', 'observed_end',
                'VV', 'VH', 'label_source', 'label_available_at'}
    if not required <= set(frame):
        raise ValueError(f'Missing columns: {sorted(required-set(frame))}')
    if frame[list(required-{'VV', 'VH'})].isna().any().any():
        raise ValueError('Missing dates, labels or field metadata')
    frame = frame.copy()
    if frame.duplicated(['field_id', 'observed_start']).any():
        raise ValueError('Duplicate field/window records')
    if not set(frame.split) <= {'train', 'test'} or set(frame.split) != {'train', 'test'}:
        raise ValueError('Explicit train/test field partitions required')
    dates = pd.to_datetime(frame.observed_start, utc=True)
    ends = pd.to_datetime(frame.observed_end, utc=True)
    if (ends <= dates).any():
        raise ValueError('Invalid observation windows')
    frame['label_available_at'] = pd.to_datetime(frame.label_available_at, utc=True)
    for key in ['block_id', 'rice', 'split', 'label_source', 'label_available_at']:
        if (frame.groupby('field_id')[key].nunique() != 1).any():
            raise ValueError(f'Field metadata changes within season: {key}')
    meta = frame.drop_duplicates('field_id').set_index('field_id').sort_index()
    vv = frame.pivot(index='field_id', columns='observed_start', values='VV').sort_index().sort_index(axis=1)
    vh = frame.pivot(index='field_id', columns='observed_start', values='VH').reindex(index=vv.index, columns=vv.columns)
    calendar = pd.to_datetime(vv.columns, utc=True)
    x = rice_features(vv.to_numpy(), vh.to_numpy(), (calendar-calendar.min()).days.to_numpy())
    train = (meta.split == 'train').to_numpy()
    # This command is explicitly end-of-season retrospective classification.
    # For in-season forecasts, build separate prefix datasets and label vintages.
    _, probability, scores = fit_rice_classifier(x[train], meta.rice.to_numpy()[train], meta.block_id.to_numpy()[train],
        x[~train], meta.rice.to_numpy()[~train], meta.block_id.to_numpy()[~train])
    output = meta.loc[~train, ['rice', 'block_id', 'label_source']].copy()
    output['rice_probability'] = probability
    scores['mode'] = 'retrospective_end_of_season_spatial_holdout'
    scores['feature_window_end'] = str(ends.max())
    scores['label_warning'] = 'Map-derived labels measure agreement, not independent field accuracy'
    return output.reset_index(), scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['moisture', 'rice'])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Choose a new output directory; existing results are immutable')
    data = pd.read_csv(args.input)
    table, details = fit_moisture(data) if args.mode == 'moisture' else classify_rice(data)
    args.output.mkdir(parents=True)
    table.to_csv(args.output/'predictions.csv', index=False)
    (args.output/'model_report.json').write_text(json.dumps(details, indent=2, allow_nan=False)+'\n')
    (args.output/'provenance.json').write_text(json.dumps({
        'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(), 'input_file': str(args.input),
        'mode': args.mode, 'rows': len(data), 'real_world_validated': False,
        'note': 'No inference about publication readiness or operational suitability.'}, indent=2)+'\n')
    print(args.output)


if __name__ == '__main__':
    main()
