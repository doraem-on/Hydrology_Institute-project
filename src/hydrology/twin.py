"""Availability-aware observation joins and auditable allocation experiments."""
import numpy as np
import pandas as pd


def available_observations(observations, issue_time, *, max_age_days=32):
    """Use only completed, available observations; return latest per unit/variable.

    Required: unit_id, variable, observed_at (END of observation support),
    available_at, value, source_id. Revised products need actual vintage records.
    """
    required = {"unit_id", "variable", "observed_at", "available_at", "value", "source_id"}
    if not required <= set(observations.columns) or max_age_days < 0:
        raise ValueError("Missing observation schema or invalid maximum age")
    frame = observations.copy()
    for column in ("observed_at", "available_at"):
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="raise")
        if frame[column].isna().any():
            raise ValueError("Observation timestamps cannot be missing")
    if (frame.available_at < frame.observed_at).any():
        raise ValueError("Availability cannot precede the observation interval end")
    if frame[["unit_id", "variable", "source_id"]].isna().any().any():
        raise ValueError("Observation identifiers cannot be missing")
    issue = pd.Timestamp(issue_time)
    issue = issue.tz_localize("UTC") if issue.tzinfo is None else issue.tz_convert("UTC")
    frame["age_days"] = (issue-frame.observed_at).dt.total_seconds()/86400
    values = pd.to_numeric(frame.value, errors="coerce")
    keep = (frame.available_at <= issue) & (frame.age_days >= 0) & (frame.age_days <= max_age_days) & np.isfinite(values)
    frame = frame.loc[keep].assign(value=values[keep])
    if frame.duplicated(["unit_id", "variable", "observed_at", "available_at"]).any():
        raise ValueError("Ambiguous duplicate observation vintage")
    return frame.sort_values(["observed_at", "available_at"]).drop_duplicates(["unit_id", "variable"], keep="last")


def demand_scenarios(area_ha, rice_fraction, wetness_index, *, dry_rice_mm, dry_other_mm,
                     wetness_response, efficiency):
    """User-specified DEMAND SCENARIO, not a calibrated irrigation requirement.

    1 ha mm = 10 m3. Surface wetness is not root-zone moisture; the response
    coefficient must be independently calibrated before real recommendations.
    Inputs broadcast to scenario x management-unit arrays if desired.
    """
    arrays = np.broadcast_arrays(*[np.asarray(a, float) for a in
                                  (area_ha, rice_fraction, wetness_index, dry_rice_mm, dry_other_mm)])
    area, rice, wetness, rice_mm, other_mm = arrays
    if (not all(np.isfinite(a).all() for a in arrays)
            or np.any(area < 0) or np.any(rice_mm < 0) or np.any(other_mm < 0)
            or np.any((rice < 0) | (rice > 1)) or np.any((wetness < 0) | (wetness > 1))
            or not np.isfinite([efficiency, wetness_response]).all()
            or not 0 < efficiency <= 1 or not 0 <= wetness_response <= 1):
        raise ValueError("Invalid demand scenario parameters")
    depth = (rice*rice_mm+(1-rice)*other_mm)*(1-wetness_response*wetness)
    return area*10*depth/efficiency


def allocate_water(flow_cms, demand_m3, *, environmental_flow_cms, diversion_fraction,
                   period_seconds=86400, risk_quantile=0.1):
    """One-reach allocation baseline, no reservoirs/routing/return-flow claims.

    Uses a lower supply quantile and a proportional-shortage rule. Environmental
    reserve precedes diversion. The cap limits abstraction to a fraction of
    water remaining above the reserve; it is not a legal entitlement.
    """
    flows, demand = np.asarray(flow_cms, float), np.asarray(demand_m3, float)
    if (flows.ndim != 1 or demand.ndim != 1 or not len(flows) or not len(demand)
            or not np.isfinite(flows).all() or not np.isfinite(demand).all()
            or (flows < 0).any() or (demand < 0).any()
            or not np.isfinite([environmental_flow_cms, diversion_fraction, period_seconds, risk_quantile]).all()
            or environmental_flow_cms < 0 or not 0 <= diversion_fraction <= 1
            or period_seconds <= 0 or not 0 <= risk_quantile <= 1):
        raise ValueError("Invalid supply, demand or allocation controls")
    supply = max(float(np.quantile(flows, risk_quantile))-environmental_flow_cms, 0)*period_seconds*diversion_fraction
    ratio = min(supply/demand.sum(), 1) if demand.sum() else 1.
    allocation = demand*ratio
    return {"allocation_m3": allocation, "unmet_m3": demand-allocation,
            "supply_budget_m3": supply, "satisfaction_fraction": float(ratio),
            "risk_quantile": risk_quantile, "environmental_flow_cms": environmental_flow_cms}


def bucket_step(storage_mm, rainfall_mm, irrigation_mm, potential_et_mm, *, capacity_mm):
    """Mass-conserving single-bucket baseline; lacks routing/paddy ponding."""
    storage, rain, irrigation, et = np.broadcast_arrays(*[np.asarray(a, float) for a in
                                                         (storage_mm, rainfall_mm, irrigation_mm, potential_et_mm)])
    if (not np.isfinite(capacity_mm) or capacity_mm <= 0
            or not all(np.isfinite(a).all() for a in (storage, rain, irrigation, et))
            or any((a < 0).any() for a in (storage, rain, irrigation, et))
            or (storage > capacity_mm).any()):
        raise ValueError("Invalid bucket inputs")
    water = storage+rain+irrigation
    runoff = np.maximum(water-capacity_mm, 0)
    retained = water-runoff
    actual_et = np.minimum(et, retained)
    end = retained-actual_et
    residual = storage+rain+irrigation-runoff-actual_et-end
    return {"storage_mm": end, "runoff_mm": runoff, "actual_et_mm": actual_et,
            "mass_balance_residual_mm": residual}


def plan_from_observations(observations, issue_time, units, flow_samples_cms, *,
                           environmental_flow_cms, diversion_fraction,
                           dry_rice_mm, dry_other_mm, wetness_response, efficiency,
                           max_age_days=32, risk_quantile=0.1):
    """Connect crop/moisture state to a hypothetical allocation scenario.

    units: DataFrame with unique unit_id and area_ha. Observations use variables
    rice_fraction and surface_wetness; optional flood_fraction and
    slope_change_fraction cause a review flag, never an automatic safety action.
    Missing/stale core observations cause abstention, not a zero-demand estimate.
    The forecast samples must be issued at issue_time from a causal model.
    """
    if not {'unit_id', 'area_ha'} <= set(units) or units.empty or units.unit_id.isna().any() or units.unit_id.duplicated().any():
        raise ValueError('Unique management unit IDs and area_ha are required')
    latest = available_observations(observations, issue_time, max_age_days=max_age_days)
    state = latest.pivot(index='unit_id', columns='variable', values='value').reindex(units.unit_id)
    for variable in ['rice_fraction', 'surface_wetness']:
        if variable not in state:
            state[variable] = np.nan
    missing = state[['rice_fraction', 'surface_wetness']].isna().any(axis=1)
    if missing.any():
        return {'status': 'insufficient_observations', 'missing_units': state.index[missing].tolist(),
                'allocation': None, 'issue_time': str(issue_time)}
    demand = demand_scenarios(units.area_ha.to_numpy(float), state.rice_fraction.to_numpy(),
        state.surface_wetness.to_numpy(), dry_rice_mm=dry_rice_mm, dry_other_mm=dry_other_mm,
        wetness_response=wetness_response, efficiency=efficiency)
    plan = allocate_water(flow_samples_cms, demand, environmental_flow_cms=environmental_flow_cms,
                           diversion_fraction=diversion_fraction, risk_quantile=risk_quantile)
    review = []
    for variable in ['flood_fraction', 'slope_change_fraction']:
        if variable in state:
            values = state[variable]
            if ((values.dropna() < 0) | (values.dropna() > 1)).any():
                raise ValueError('Hazard fractions must be between zero and one')
            for unit in state.index[values > 0]:
                review.append({'unit_id': unit, 'reason': variable, 'action': 'verify_candidate_layer'})
    return {'status': 'hypothetical_scenario_not_operational_advice', 'issue_time': str(issue_time),
            'unit_ids': units.unit_id.tolist(), 'demand_m3': demand.tolist(),
            'allocation': {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in plan.items()},
            'review_flags': review,
            'observation_provenance': latest.assign(observed_at=latest.observed_at.astype(str),
                available_at=latest.available_at.astype(str)).to_dict(orient='records')}
