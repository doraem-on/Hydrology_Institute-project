# Gandak warning experiment

The [combined manuscript](../../paper/water_resources/manuscript.md) reports the 2026 Gandak and Potomac decision experiments. This directory holds the hourly test predictions and primary verification tables. All local issue and onset timestamps in these outputs use India standard time (UTC+05:30).

## Reproduce

Run from the repository root in the project environment. The download is read-only, takes about 90 daily requests to each provider, and caches completed days under the git-ignored data/raw/gandak_inputs directory. The original pilot's archived barrage input is already in the repository.

```sh
.venv/bin/python scripts/fetch_gandak_inputs.py
PYTHONPATH=src .venv/bin/python -m hydrology.gandak_warning
PYTHONPATH=src .venv/bin/python -m hydrology.gandak_warning --rain-delay 24 --output results/gandak_warning/rain_delay_24h
PYTHONPATH=src .venv/bin/python scripts/research_sensitivity.py
.venv/bin/python -m pytest -q
```

The first command writes gauge.csv and rain.csv. Compare their SHA-256 digests with run.json before comparing numerical results. The local input snapshot is retained in the project's data folder. Public archives may change. The published forecasts and CSVs can be inspected offline.

## Source and coverage

* Barrage inflow in m³/s uses the [CWC archive and cleaning record](../gandak_hourly/README.md). These archived target records carry observation times but no historical release timestamps. The analysis assumes the last recorded local inflow was available at issue.
* Upstream gauge heights in metres are Nepal Department of Hydrology and Meteorology observations via the [BIPAD historical river endpoint](https://bipadportal.gov.np/api/v1/river/?station=25), station 25, series 4140, [Narayani at Devghat](https://dhm.gov.np/hydrology/hms-Single/265). The ingestion query verified station and date. It found 10,466 records from July 30 to October 21 UTC. Filter on the latest of measurement, creation and modification times. A later revision cannot enter an earlier issue. Gauge heights are in the station's reference datum. Two-hour freshness applies separately to current and six-hour-lagged observations. Service timestamps are a proxy for access, not an independent audit of bulletin delivery.
* NOAA GFS Global forecasts were obtained via [Open-Meteo single runs](https://open-meteo.com/en/docs/single-runs-api), with [Open-Meteo attribution](https://open-meteo.com/en/terms). Ninety dated 00 UTC cycles from July 30 to October 27 each contain three point series and 120 hourly endpoints. Requested coordinates are (28.21, 83.99), (28.23, 84.38), (28.00, 84.63). The equal-weight point mean is an index of mid-basin forecast precipitation. Hourly precipitation is in mm. No observed or reanalysis rain enters the predictors. A cycle is eligible at least 12 hours after initialization in the main run and 24 hours after initialization in the sensitivity run. These are release assumptions. A forecast issue at half past UTC uses rainfall interval endpoints up to the integer UTC hour at the end of its lead.

## How to read the outputs

* scores.csv includes the chronological training count, matched test count, and eligible barrage-only count for every lead. Test issues run from September 16 at 00:00 to October 22 at 00:00 IST on the common sample. Forecasts at missing-input hours are excluded. All four regressions are refitted with identical training rows per lead, using the original ridge formulation. This explains why local-only scores and event predictions differ slightly from the earlier pilot. Compare methods within the same table.
* alerts.csv and onsets.csv use the 95th percentile of training inflow; threshold_sensitivity.csv also reports the 90th and 99th. An alert at an hourly decision predicts any crossing in the following 24 hours from below the threshold. A false alert is an issue without a subsequent observed crossing in this window. Repeated positive decisions for one flood are not independent warnings. Onset counts require 24 complete preceding hours below the threshold. First-warning lead is measured to the onset, not to the later crest. These thresholds do not confer official flood-warning status.
* september_forecast.csv records all 72 predictions at the pre-existing example issue. september_crest.csv reports each series' first maximum. For persistence the peak is flat and its first maximum does not describe meaningful timing.
* paired_intervals.csv reports descriptive 95% intervals at five leads. Paired hourly absolute-error differences are summed by calendar day with observation counts, then resampled in circular blocks of three days with 2,000 draws (seed 20261110). This retains some serial dependence but cannot compensate for a single flood season or a previously inspected event.
* rain_delay_24h contains summary results for the delayed-release assumption. scripts/research_sensitivity.py also reproduces the Potomac flow-band coverage and allocation-cost tables from archived daily forecasts and decisions.
