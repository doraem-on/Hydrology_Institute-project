# Hydrology Institute project

## River-basin digital-twin extension

The [implementation and research protocol](docs/digital_twin.md) adds SAR
rice classification, MODIS/TOTRAM surface wetness, flood and landslide candidate
screening, optical turbidity indices, observation-availability checks and
allocation scenarios. Earth Engine exports are in `earth_engine/`; actual
satellite execution and independent field validation remain outstanding.
The existing Potomac flow benchmark is preserved. Its new allocation replay
uses explicitly hypothetical demand and policy, not a validated basin plan.

The [working manuscript](paper/river_basin_digital_twin/main.tex) contains the
implemented methods and exploratory replay results, with unfinished satellite
validation clearly marked. The [replay report](results/decision_replay_20261027/report.json)
and [validation record](results/decision_replay_20261027/implementation_validation.json)
record the current evidence. Open the manuscript folder in the LaTeX editor.

```bash
uv pip install --python .venv/bin/python -r requirements-satellite-lock.txt
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m hydrology.decision_replay --output results/my_decision_replay
```

## Existing streamflow benchmark

This repository implements next-day streamflow forecasting with LSTM, stacked
LSTM, bidirectional LSTM and a Transformer, followed by calibrated forecast
Bayesian model averaging (BMA). It also records the data sources from the
constructed-wetland phosphorus proposal.

The first experiment uses **USGS station 01646500, Potomac River near Washington,
DC**, with daily mean discharge from 1990–2025. This is a single-station,
historical benchmark. It does not validate phosphorus retention or transfer to
an unfamiliar catchment.

## Run

Use Python 3.11 or newer. The recorded run used Python 3.12 on CPU.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
python -m hydrology.data
python -m pytest -q
python -m hydrology.train --output results/my_run
```

The archived USGS response is included, so preprocessing and training work
offline after dependency installation. To intentionally retrieve fresh source
data, use `python -m hydrology.data --download`. The upstream API may change;
the archived response and recorded checksum preserve this experiment.

Training refuses to overwrite a nonempty result directory. Local model
checkpoints are saved in that run's `checkpoints` folder and excluded from Git.
Metrics, daily predictions, calibration predictions, learning curves, BMA
parameters, source checksums and a hydrograph are saved with each run.

## Experimental design

| Partition | Target dates | Purpose |
| --- | --- | --- |
| Training | 1990–2009, after the initial history window | Scaling and neural-network fitting |
| Validation | 2010–2014 | Epoch selection and early stopping |
| Calibration | 2015–2019 | BMA bias corrections, mixture weights and variance; base-model mean correction |
| Test | 2020–2025 | Final metrics only |

Each forecast uses the preceding 30 observed daily flows and historical calendar
features. The networks predict a correction to the last observed standardized
`log1p` flow. All networks use width 32, Adam, up to 20 epochs and validation
early stopping. Their parameter counts differ; this is an initial architecture
comparison, not a matched-capacity study.

The test is a **rolling next-day hindcast**: once a test day has passed, its
observed discharge can enter the next forecast's history. This is not a
six-year forecast issued in 2019. Historical revised daily values also do not
prove real-time data availability. No future observed streamflow enters an
input window, including in the bidirectional model and Transformer.

## Read the work

- [First experiment and limitations](docs/first_experiment.md)
- [Algorithms and working principles](docs/algorithms.md)
- [Dataset downloads, access status and attribution](docs/datasets.md)
- [Machine-readable data manifest](data/manifest.json)

## Research status

The four models and forecast BMA have been implemented and run. Ten focused
tests cover window chronology, train-only scaling, missing dates, source flags,
model gradients, mixture fitting and distribution calculations. Results come
from one fixed split and seed; they are an initial benchmark, not a completed
research study. Multi-seed experiments, other stations, meteorological inputs,
longer lead times and rolling-origin evaluation remain future work.

Downloaded third-party data retain their source attribution and applicable
terms. The proposal PDF and private correspondence are not included.
