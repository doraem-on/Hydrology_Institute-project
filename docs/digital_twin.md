# River-basin digital twin: implementation and research protocol

Status, 27 October 2026: executable research extension; satellite validation
and a complete manuscript are outstanding. A software prototype cannot
establish novelty or publication acceptance by itself.

## Recovered project context

The existing repository contains a Potomac River daily streamflow benchmark
(USGS 01646500, 1990–2025), four neural models, calibrated forecast BMA, and saved
2020–2025 predictions. It also records a separate constructed-wetland proposal.
Neither is evidence that Potomac was chosen for a rice-mapping study. No existing
digital-twin manuscript, verified basin boundary, rice labels, paired soil
measurements, or Earth Engine credentials were found during the local search.
The available records do not justify inventing those inputs or merging the
wetland study into the new project.

The Potomac remains the **existing flow benchmark only**. Before a satellite
case study, choose a catchment with observed discharge, substantial paddy area,
verified crop references, and soil-moisture validation. A basin must be delineated
from an authoritative catchment product or hydrological delineation, not named
after an arbitrary map rectangle. A flood/landslide case study may require a
different event or subbasin; distinguish cross-basin experiments explicitly.

## Proposed contribution

Working title: **From satellite observations to water-allocation decisions:
an availability-aware river-basin digital-twin framework**.

Research question: Under what data quality and observation delay conditions do
crop and surface-moisture observations improve allocation outcomes relative to
a flow-only baseline, and when should the system abstain?

The proposed contribution is the controlled decision evaluation, provenance,
and failure analysis. Crop classifiers, TOTRAM, SAR change detection, NDTI,
neural flow forecasts, and digital twins are established approaches. Do not
claim to be the first to combine them. The literature scan below is preliminary,
not a systematic novelty review. A narrowly evaluated contribution will be
stronger than a broad collection of maps with no independent validation.

## What is implemented

| Component | Implementation | Scientific limit |
| --- | --- | --- |
| Rice/paddy classification | Monthly dual-polarization SAR features, train-only imputation, random forest, disjoint spatial evaluation groups, F1/balanced accuracy/AP/Brier/confusion matrix | Needs independent labels; RF scores are not calibrated uncertainty; seasonal model is retrospective |
| Surface moisture | MODIS QA/scaling, scene-specific conditional quantile wet/dry edges, TOTRAM relative index, unsupported-scene rejection | Dimensionless surface index, not volumetric or root-zone moisture; needs wet/dry coverage and weather/elevation stratification |
| Flood screening | Same-orbit before/after SAR darkening, absolute water threshold, slope/permanent-water masks, connected components | Candidate extent only; fails for some urban/vegetated/double-bounce floods |
| Turbidity | Cloud-screened optical NDTI restricted to water | Index only; NTU/TSS requires locally validated calibration and atmospheric correction suitable for water |
| Landslide screening | Terrain-masked bidirectional SAR amplitude-change candidates | Not a confirmed inventory, prediction, coherence product or displacement estimate |
| Twin state | Observation support end, availability/vintage checks, provenance and staleness | Historical revised products cannot establish real-time availability |
| Decision support | Crop/wetness demand scenarios, lower-quantile supply budgets, environmental reserve, proportional shortage, missing-data abstention | Single-reach scenario; uncalibrated demand, no operational/rights recommendation |
| Water balance | Mass-conserving bucket with bounded storage and water-limited ET | No channel routing, groundwater, percolation or paddy ponding model |
| Existing-flow replay | Persistence vs BMA mean vs BMA 5th percentile | Real flow forecasts with hypothetical demand/policy; no satellite-benefit claim |

The modules are in `src/hydrology/remote_sensing.py`, `twin.py`,
`satellite_pipeline.py` and `decision_replay.py`. Earth Engine export scripts are
in `earth_engine/`. They are source-reviewed and syntax-checked locally; they
have not been executed against Earth Engine in this session.

`plan_from_observations` connects crop fractions and surface wetness to the
scenario allocator. Optional flood and slope-change observations create review
flags. NDTI is a monitoring layer; it cannot restrict water use until a measured
quality threshold has been calibrated. All area fractions must come from
area-weighted aggregation on a documented common support. The code does not
silently infer area from a random satellite sample.

## Run locally

From the repository root, use the existing virtual environment:

```bash
uv pip install --python .venv/bin/python -r requirements-satellite-lock.txt
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m hydrology.decision_replay --output results/my_decision_replay
PYTHONPATH=src .venv/bin/python -m hydrology.satellite_pipeline moisture --input data/raw/totram_scene_samples.csv --output results/my_totram
PYTHONPATH=src .venv/bin/python -m hydrology.satellite_pipeline rice --input data/raw/rice_field_sar_observations.csv --output results/my_rice
```

The last two commands require actual exported inputs; they are not included as
fabricated datasets. Output directories must not already exist. The classifier
can be used without Earth Engine if equivalent co-registered SAR features and
verified labels are supplied. Tests use explicitly synthetic fixtures only.

To reproduce the whole environment, install `requirements-lock.txt` before the
satellite lock file. Neither running tests nor the flow replay starts an Earth
Engine task, uploads private data, or publishes repository changes.

### Earth Engine acquisition

1. Use an authorized Earth Engine account and registered project.
2. Import a verified `roi` geometry. For crop exports also import field polygons
   with `field_id`, `block_id`, `rice` (0/1), `split` (train/test), `label_source`,
   and `label_available_at`. Assign blocks with buffers to reduce boundary
   dependence, not a new ID per adjacent pixel. Preserve field delineation and
   labels separately from feature rasters.
3. Set dates, one relative orbit and pass after checking local coverage. For
   event rasters also set a suitable local projected CRS. All example dates and
   numerical thresholds are starting controls, not selected case-study findings.
4. Run the export scripts, inspect scene counts and quality coverage, then start
   the desired Drive export tasks. A successful task is required before claiming
   satellite execution. Store raw exports unchanged and record task IDs, asset
   IDs, code revision, geometry checksum, timestamps, CRS, support and masks.
5. The MODIS export keeps approximately 1 km support and matches complete 8-day
   LST windows inside the 16-day vegetation interval. This is a composite-based
   approximation, not simultaneous temperature/vegetation acquisition. Compare
   with daily, contemporaneous products in sensitivity analysis.
6. Fit moisture edges per scene/elevation stratum. Inspect rejected bins, edge
   slopes, clipped pixels, clouds and spatial representativeness before mapping.
   The fit is from sampled pixels; it is not automatically an area-average map.
7. Use `observed_end` as observation support end. The export intentionally marks
   availability as `unverified_historical`. Add actual release/vintage times for
   operational replay, or explicitly label assumed-latency experiments. Never
   use a 16-day composite at the beginning of its observation interval.

SAR input is calibrated Earth Engine GRD backscatter in dB. Differences are log
power ratios; dividing two negative dB values is not a physical power ratio.
Terrain correction in GRD is not complete radiometric terrain flattening or a
layover/shadow mask. Those effects need dedicated review, especially in mountains.

### Required state schema

One row per management unit, variable, observation and release vintage:

```text
unit_id,variable,observed_at,available_at,value,source_id
```

`observed_at` means the observation interval END. `available_at` must be at or
after it. Use variables `rice_fraction`, `surface_wetness` and optionally
`flood_fraction`/`slope_change_fraction`. Area-weighted rice probabilities are
not automatically unbiased crop-area estimates; report design-based accuracy
and area uncertainty. Missing/stale crop or wetness rows cause abstention.
Observation errors and spatial correlation need empirical calibration before
propagating probability distributions into decisions.

## Evaluation that could make the paper distinctive

Predefine outcomes before inspecting the new final holdout. The old Potomac
test has already been examined and should not become the tuning set for a new
claim. Use new held-out catchments/events or nested rolling-origin evaluation.

| Experiment | Comparison | Primary outcome |
| --- | --- | --- |
| Crop information | Full model vs fixed crop fractions | Change in allocation loss and shortage distribution |
| Moisture information | Full model vs no wetness response | Same decision metrics; surface-index skill separately |
| Observation latency | Measured availability, then additional 3/7/14/30-day delays | Degradation and abstention curves |
| Missing data | Structured cloud/coverage gaps and sensor outages | Decision reliability vs coverage |
| Supply uncertainty | Mean vs preselected lower quantiles | Overcommitment vs unmet-demand tradeoff |
| Crop/edge uncertainty | Calibrated correlated perturbations vs point inputs | Sensitivity of unit-level allocations |
| Transfer | Withheld spatial blocks, seasons and catchments | Out-of-domain skill and failure strata |

For each comparison keep forcings, demands, scenario horizon and resource
constraints identical. Do not give one variant access to later observations.
Run several prespecified seeds and use paired hydrological block bootstrap
intervals, not independent resampling of neighboring pixels or consecutive
days. Choose block lengths from temporal dependence analysis on training data.

**Independent validation:**

- Rice: held-out field survey/reference polygons with sampling design and label
  uncertainty; map-derived labels alone demonstrate map agreement.
- Moisture: compare with collocated in-situ surface observations; calibrate any
  conversion using training locations only. SMAP can be a coarse comparison,
  not field-scale ground truth. Match depth, footprint and overpass time.
- Floods: independent dated flood outlines; report precision, recall, IoU and
  omission in vegetation/urban classes, with acquisition timing accounted for.
- Turbidity: paired laboratory/sensor NTU or TSS, time-matched reflectance,
  withheld sites and event blocks. Avoid transferring calibration coefficients
  between waters without evidence.
- Landslides: independently mapped event polygons and negative controls. Report
  candidate-screening performance; exclude radar shadow/layover or report them
  as unsupported coverage. Do not call amplitude change an InSAR measurement.
- Flow: retain persistence and seasonal baselines, NSE/KGE/RMSE, low/high-flow
  strata, interval coverage and proper probabilistic scores.
- Decisions: shortage, overcommitment, reserve violation, distribution across
  units, and regret against a clearly defined offline perfect-information bound.
  Report modelled benefits as simulation results, not actual water saved.

## Manuscript structure and claim boundaries

1. Introduction: specific decision problem and testable hypothesis; distinguish
   prediction accuracy from decision value.
2. Related work: basin twins, data latency/assimilation, crop mapping, moisture
   retrieval and uncertainty-aware allocation; provide a comparison matrix.
3. Study area/data: actual basin boundary, monitoring network, dates, observation
   supports, release times, licences and independent reference samples.
4. Methods: observation-to-state-to-decision loop; feature/edge fitting, causal
   joins, constraints, uncertainty and abstention. Describe prototype limits.
5. Experiments: locked partitions, baselines, ablations, latency/missingness
   perturbations, uncertainty intervals and computation costs.
6. Results: fill only after runs; include negative results and failure cases.
7. Discussion: transfer, coarse-resolution mixing, label errors, rainfall and
   governance constraints; prototype vs operational deployment.
8. Reproducibility: code, exact environment, data manifests, configurations and
   an explicit statement of unavailable/protected datasets.

Planned figures: study-area/support map; state/decision architecture; observed
vs estimated crop and moisture panels with uncertainty; latency–loss curve;
allocation tradeoff; ablation intervals; failure-case map. The generated
`decision_tradeoff.png` is only an exploratory figure from saved flow forecasts.

Do not write a results-bearing abstract or claim operational water savings,
novelty, superiority, real-time synchronization or publication readiness until
the corresponding evidence exists. The current implementation provides the
experiment infrastructure, not those findings.

## Source register

Primary research and official documentation consulted on 27 October 2026:

- Yang et al. (2024), *Digital twinning of river basins towards full-scale,
  sustainable and equitable water management and disaster mitigation*.
  [DOI: 10.1038/s44304-024-00047-2](https://doi.org/10.1038/s44304-024-00047-2).
  Basin-twin architectures already include data, model and decision layers.
- [IWMI digital twins](https://www.iwmi.org/topics/digital-twins/): existing
  water allocation, scenario and uncertainty applications; combination is not
  itself a novelty claim.
- Sadeghi et al. (2017), *The optical trapezoid model: A novel approach to remote
  sensing of soil moisture applied to Sentinel-2 and Landsat-8 observations*.
  [Publisher](https://www.sciencedirect.com/science/article/pii/S0034425717302493).
  Distinguish thermal TOTRAM from optical OPTRAM; scene calibration matters.
- *A Comparison of Three Trapezoid Models Using Optical and Thermal Satellite
  Imagery for Water Table Depth Monitoring in Estonian Bogs* (2020).
  [Methods/equations](https://www.mdpi.com/2072-4292/12/12/1980).
- [Sentinel-1 preprocessing](https://developers.google.com/earth-engine/guides/sentinel1),
  [MOD13A2](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A2),
  [MOD11A2](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2):
  metadata, QA, resolution and product support.
- [UN-SPIDER flood-mapping practice](https://un-spider.org/advisory-support/recommended-practices/recommended-practice-google-earth-engine-flood-mapping/in-detail).
- *Sentinel-1 SAR Amplitude Imagery for Rapid Landslide Detection* (2019).
  [Research and limitations](https://www.mdpi.com/2072-4292/11/7/760).
- *A Comparison of Non-Contact Methods for Measuring Turbidity in the Colorado
  River* (2026). [Research](https://www.mdpi.com/2072-4292/18/4/638).

Screenshot learning resources (identified by title; implementations here are
independent baselines, not claimed reproductions of unseen video code):

- Rice/paddy classification using Sentinel-1: visible preview; exact URL absent.
- [Rapid flood mapping](https://youtu.be/c3_UlwEwEoE).
- [Turbidity tutorial](https://youtu.be/_PJ-YaLcdlE).
- [Landslide detection tutorial](https://youtu.be/hz6yA2NT52k).
- MODIS soil-moisture tutorial 214 (TOTRAM): visible preview; exact URL absent.
- `lky4pyoY1mc`/`Iky4pyoY1mc`: screenshot character ambiguous; not identified.
- `rHTF45OkYRs`: linked from a GESTAR report as a soil-moisture mapping talk;
  video content not retrieved. No additional algorithm attributed to it.
