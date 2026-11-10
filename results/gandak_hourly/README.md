# Hourly inflow forecasting at Gandak Barrage

Historical research pilot. Each issue time has predictions at 1–72 hours. The target is **barrage inflow** (m³/s). Downstream releases can differ because the barrage is operated. The October WRD bulletin is context, not a source of training labels. The Potomac daily benchmark is a separate experiment.

## Data and attribution

Underlying readings: Central Water Commission Flood Forecast System, via the [November 2026 public archive](https://github.com/diagram-chasing/cwc-flood-forecasts) and its [data dictionary](https://github.com/diagram-chasing/cwc-flood-forecasts/blob/main/DATA.md). The compilation is published under the Open Database License. Parameter names are the archive maintainer’s mapping. Verify the target definition with WRD before comparing to its downstream-discharge bulletin.

`source_inflow.csv` is an extract of [hourly.parquet](https://diagram-chasing.github.io/cwc-flood-forecasts/hourly.parquet), SHA-256 `57b71f7cba501e2218278f458c61f8002f21d971dd644d60bc5a0a47838e6e66`. Select station `061-MGD4PTN` (GANDAK BARRAGE, 27.43 N, 83.9 E), code `FIN`, variable `reservoir_inflow`, unit `cumec`. Timestamps are IST. The study period runs from August 1 00:00 to October 27 14:00, 2026. Earlier records were mostly once daily. The separate `FOL` outflow series had only 08:00 observations in 2026 in this snapshot.

Of 2,103 hourly slots, 2,102 have a source record. August 4 at 05:00 is missing. The raw extract preserves one suspect value of 339,091 m³/s on August 3 at 01:00, between 3,592.05 and 3,390.91 m³/s. We excluded it without substituting an estimate. Consecutive readings often repeat, so a timestamp every hour does not establish a fresh independent measurement every hour. This archive does not record when historical values or revisions became available in real time.

## Experiment

From the project root, run `PYTHONPATH=src .venv/bin/python -m hydrology.gandak_hourly`. The method fits a separate ridge regression for each lead using only the current inflow and changes over the past 1, 3, 6, 12 and 24 hours. It requires a complete 25-hour history. Inputs are standardized on the training partition. All training targets precede September 16 at 00:00 IST. Forecasts issued from that instant onward are evaluated against archived values at their exact valid hour, with no interpolation. A persistence forecast uses the last reading for every lead. This is a retrospective rolling-origin test with fixed coefficients, one season, and no rainfall or gate-operation inputs.

`metrics_by_lead.csv` reports MAE and RMSE in m³/s, with the number of training and test pairs per lead. `heldout_predictions.csv.gz` contains all compared predictions. `september_event.csv` and its plot show the 72-hour forecast issued September 27 at 14:00 IST as a specific flood example. The last-reading baseline had lower MAE at 1, 6, 12, 24, 48 and 72 hours. The regression had lower RMSE at 48 and 72 hours, but missed the September flood crest. These errors characterize inflow over the study interval; they do not establish performance across monsoons or for downstream discharge.
