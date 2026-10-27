"""Array kernels for co-registered, quality-screened satellite observations.

These are established baselines, not validated products for a particular basin.
NaN denotes an unobserved/invalid pixel; zero is never used as missing data.
"""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import label


def _arrays(*values):
    arrays = tuple(np.asarray(v, dtype=float) for v in values)
    if len({a.shape for a in arrays}) != 1:
        raise ValueError("Inputs must be co-registered and have identical shapes")
    return arrays


def normalized_difference(a, b):
    a, b = _arrays(a, b)
    valid = np.isfinite(a) & np.isfinite(b) & (a >= 0) & (b >= 0) & (a+b > 1e-10)
    return np.divide(a-b, a+b, out=np.full(a.shape, np.nan), where=valid)


def ndti(red, green, water_mask):
    """Dimensionless turbidity proxy. NOT NTU, TSS or a water-safety measure."""
    red, green, water = _arrays(red, green, water_mask)
    return np.where(water == 1, normalized_difference(red, green), np.nan)


def modis_quality(ndvi_raw, summary_qa, lst_raw, qc_day):
    """MOD13A2 + MOD11A2 scale/strict QA; temporal alignment is caller's job."""
    ndvi, qa, lst, qc = _arrays(ndvi_raw, summary_qa, lst_raw, qc_day)
    q = np.where(np.isfinite(qc), qc, 255).astype(np.int64)
    good_vi = (qa == 0) & (ndvi >= -2000) & (ndvi <= 10000)
    good_lst = (np.isfinite(qc) & ((q & 3) == 0) & (((q >> 2) & 3) == 0)
                & (((q >> 6) & 3) == 0) & (lst > 0))
    valid = good_vi & good_lst
    return np.where(valid, ndvi*0.0001, np.nan), np.where(valid, lst*0.02, np.nan)


@dataclass(frozen=True)
class Trapezoid:
    wet_intercept: float
    wet_slope: float
    dry_intercept: float
    dry_slope: float
    ndvi_min: float
    ndvi_max: float
    fitted_pixels: int
    fitted_bins: int

    def moisture_index(self, ndvi, lst_kelvin):
        """Relative surface wetness [0,1]; no volumetric/root-zone conversion."""
        vi, temperature = _arrays(ndvi, lst_kelvin)
        wet = self.wet_intercept + self.wet_slope*vi
        dry = self.dry_intercept + self.dry_slope*vi
        valid = (np.isfinite(vi) & np.isfinite(temperature) & (temperature > 0)
                 & (vi >= self.ndvi_min) & (vi <= self.ndvi_max) & (dry-wet >= 1))
        raw = np.divide(dry-temperature, dry-wet, out=np.full(vi.shape, np.nan), where=valid)
        return {"moisture_index": np.clip(raw, 0, 1), "unclipped_index": raw,
                "outside_edges": np.isfinite(raw) & ((raw < 0) | (raw > 1)),
                "valid": valid}


def fit_trapezoid(ndvi, lst_kelvin, *, bins=10, min_per_bin=20,
                  quantiles=(0.05, 0.95)):
    """Fit scene-specific wet/dry edges from conditional temperature quantiles.

    Fit separately within approximately homogeneous weather/elevation strata.
    This statistical edge estimator is a baseline, not a claim of universal
    physical calibration. Each scene requires sufficient wet/dry coverage.
    """
    vi, temperature = _arrays(ndvi, lst_kelvin)
    if bins < 3 or min_per_bin < 5 or not 0 <= quantiles[0] < quantiles[1] <= 1:
        raise ValueError("Invalid trapezoid fitting controls")
    good = np.isfinite(vi) & np.isfinite(temperature) & (vi >= 0) & (vi <= 1) & (temperature > 0)
    vi, temperature = vi[good], temperature[good]
    if len(vi) < 3*min_per_bin or np.ptp(vi) < 0.2:
        raise ValueError("Insufficient pixels or vegetation range to identify edges")
    boundaries = np.linspace(vi.min(), vi.max(), bins+1)
    centers, wet, dry = [], [], []
    for i in range(bins):
        keep = (vi >= boundaries[i]) & (vi <= boundaries[i+1] if i == bins-1 else vi < boundaries[i+1])
        if keep.sum() >= min_per_bin:
            centers.append(float(np.median(vi[keep])))
            low, high = np.quantile(temperature[keep], quantiles)
            wet.append(low)
            dry.append(high)
    if len(centers) < 3 or np.ptp(centers) < 0.2:
        raise ValueError("Too few populated NDVI bins")
    ws, wi = np.polyfit(centers, wet, 1)
    ds, di = np.polyfit(centers, dry, 1)
    domain = np.array([min(centers), max(centers)])
    if np.any(di+ds*domain-(wi+ws*domain) < 1):
        raise ValueError("Wet/dry edges cross or have insufficient thermal separation")
    return Trapezoid(float(wi), float(ws), float(di), float(ds),
                     float(domain[0]), float(domain[1]), len(vi), len(centers))


def _components(candidate, minimum_pixels):
    if candidate.ndim != 2 or minimum_pixels < 1:
        raise ValueError("A 2-D raster and positive component size are required")
    ids, _ = label(candidate, structure=np.ones((3, 3)))
    counts = np.bincount(ids.ravel())
    return candidate & (counts[ids] >= minimum_pixels)


def flood_candidates(before_db, after_db, slope_deg, permanent_water, valid_mask,
                     *, drop_db=3., maximum_after_db=-15., max_slope_deg=5., minimum_pixels=8):
    """Dark-water change baseline; misses double-bounce/vegetated/urban floods.

    Inputs must share relative orbit, pass, polarization, grid and processing.
    Thresholds are hypotheses to calibrate on training events only.
    """
    before, after, slope, permanent, valid = _arrays(before_db, after_db, slope_deg, permanent_water, valid_mask)
    if not np.isfinite([drop_db, maximum_after_db, max_slope_deg]).all() or drop_db <= 0 or max_slope_deg < 0:
        raise ValueError("Invalid flood thresholds")
    observed = (np.isfinite(before) & np.isfinite(after) & np.isfinite(slope)
                & np.isin(permanent, [0, 1]) & (valid == 1) & (slope >= 0) & (slope <= 90))
    candidate = (observed & (before-after >= drop_db) & (after <= maximum_after_db)
                 & (slope <= max_slope_deg) & (permanent == 0))
    return np.where(observed, _components(candidate, minimum_pixels).astype(float), np.nan)


def landslide_candidates(before_db, after_db, slope_deg, valid_mask,
                         *, change_db=4., min_slope_deg=15., minimum_pixels=8):
    """SAR amplitude-change screening; NOT an inventory or InSAR displacement."""
    before, after, slope, valid = _arrays(before_db, after_db, slope_deg, valid_mask)
    if not np.isfinite([change_db, min_slope_deg]).all() or change_db <= 0 or not 0 <= min_slope_deg <= 90:
        raise ValueError("Invalid landslide thresholds")
    observed = (np.isfinite(before) & np.isfinite(after) & np.isfinite(slope)
                & (valid == 1) & (slope >= 0) & (slope <= 90))
    candidate = observed & (np.abs(after-before) >= change_db) & (slope >= min_slope_deg)
    return np.where(observed, _components(candidate, minimum_pixels).astype(float), np.nan)


def rice_features(vv_db, vh_db, day_of_season):
    """One row per field/pixel, columns from an ordered VV/VH time sequence.

    The acquisition calendar must be shared across samples; all observations
    must precede the intended issue date. Missing acquisitions are kept in the
    raw sequence and imputed using TRAINING data by the classifier pipeline.
    """
    vv, vh = _arrays(vv_db, vh_db)
    days = np.asarray(day_of_season, dtype=float)
    if (vv.ndim != 2 or vv.shape[1] < 3 or days.shape != (vv.shape[1],)
            or not np.isfinite(days).all() or np.any(np.diff(days) <= 0)):
        raise ValueError("Expected samples x time arrays and strictly increasing acquisition days")
    if np.isinf(vv).any() or np.isinf(vh).any():
        raise ValueError("Use NaN for missing SAR acquisitions")
    if np.any(np.isfinite(vv).sum(axis=1) < 3) or np.any(np.isfinite(vh).sum(axis=1) < 3):
        raise ValueError("At least three valid observations per polarization are required")
    # Difference in dB is the log power ratio, never divide dB values.
    contrast = vv-vh
    summaries = []
    for data in (vv, vh):
        summaries.extend([np.nanmedian(data, axis=1), np.nanmin(data, axis=1),
                          np.nanmax(data, axis=1), np.nanstd(data, axis=1)])
    return np.column_stack([vv, vh, contrast, *summaries])


def fit_rice_classifier(x_train, y_train, groups_train, x_test, y_test, groups_test, *, seed=42):
    """Random-forest baseline with explicit independent evaluation groups.

    Groups must encode the spatial unit (field/block), not a random pixel ID.
    Holding out years also requires constructing separate year partitions.
    Returns probabilities, not calibrated uncertainty intervals.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score
    from sklearn.pipeline import make_pipeline

    x_train, x_test = np.asarray(x_train, float), np.asarray(x_test, float)
    y_train, y_test = np.asarray(y_train), np.asarray(y_test)
    gt, ge = np.asarray(groups_train), np.asarray(groups_test)
    if (x_train.ndim != 2 or x_test.ndim != 2 or x_train.shape[1] != x_test.shape[1]
            or len(x_train) != len(y_train) or len(x_test) != len(y_test)
            or len(gt) != len(y_train) or len(ge) != len(y_test)):
        raise ValueError("Inconsistent feature, label or group dimensions")
    if set(y_train) != {0, 1} or set(y_test) != {0, 1}:
        raise ValueError("Both partitions require rice=1 and other=0 labels")
    if any(v is None or str(v).strip() in {'', 'nan'} for v in [*gt, *ge]):
        raise ValueError("Every sample requires an evaluation group")
    if set(gt) & set(ge):
        raise ValueError("Spatial leakage: train and test share groups")
    if not np.isfinite(x_train).any(axis=0).all() or np.isinf(x_train).any() or np.isinf(x_test).any():
        raise ValueError("Invalid features or entirely missing training column")
    model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                          RandomForestClassifier(n_estimators=200, min_samples_leaf=3,
                                                 class_weight="balanced", random_state=seed, n_jobs=1))
    model.fit(x_train, y_train)
    probability = model.predict_proba(x_test)[:, 1]
    predicted = (probability >= 0.5).astype(int)
    scores = {"f1": float(f1_score(y_test, predicted)),
              "balanced_accuracy": float(balanced_accuracy_score(y_test, predicted)),
              "average_precision": float(average_precision_score(y_test, probability)),
              "brier_score": float(brier_score_loss(y_test, probability)),
              "confusion_matrix_true_rows_0_1": confusion_matrix(y_test, predicted, labels=[0, 1]).tolist()}
    return model, probability, scores
