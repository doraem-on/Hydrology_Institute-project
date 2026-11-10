# Gandak validation

The original September holdout, the historical archive coverage audit, and a separately trained daily benchmark answer different questions. The original 2026 hourly forecasts can be replayed from the saved coefficients without retraining. Run from the repository root after obtaining the [original gauge and weather inputs](../gandak_warning/README.md).

    PYTHONPATH=src .venv/bin/python scripts/monsoon_transfer.py

To score an independent year, supply a folder containing source_inflow.csv (timestamp and inflow_m3s, whole hours in IST) and the season's gauge.csv and rain.csv in the original input format. Supply data across the whole evaluation window, including lead-in and verification hours as appropriate. Missing values remain missing.

    PYTHONPATH=src .venv/bin/python scripts/monsoon_transfer.py --external-barrage /path/to/barrage --inputs /path/to/gauge-and-rain --output /path/to/scores

The frozen model was created by hydrology.gandak_warning with a 12-hour GFS availability lag and a 16 September 2026 training cutoff. Copy frozen_combined.json from a fresh training output to compare it with the deposited file. The external scorer reads the deposited model. False alert runs count consecutive false decision hours. Reports distinguish missed assessable onsets from onsets with no eligible decision. The window-hours denominator includes times with missing inputs or unverifiable future labels.

historical_inflow.csv contains every 2023–2025 reading for station 061-MGD4PTN, datatype FIN, variable reservoir_inflow, unit cumec, from the [CWC archive](https://diagram-chasing.github.io/cwc-flood-forecasts/hourly.parquet) (ODbL, SHA-256 57b71f7cba501e2218278f458c61f8002f21d971dd644d60bc5a0a47838e6e66). Inputs are morning snapshots. The hourly coverage audit uses June 1 through October 31 inclusive. The daily benchmark fits 2024 only, scores 2025 only and requires consecutive mornings. A newly high morning is a crossing if the preceding morning was below the fixed 2024 threshold. Intraday onsets cannot be timed from these data.

Peak flags use the observed level available at the issue hour and the frozen training limits. Peak error compares maxima over the next 72 hours. The descriptive large-error cutoff is the test errors' 90th percentile. It is used for evaluation only. Overlapping forecast windows are dependent.
