"""Fetch public Devghat observations and individual GFS forecasts for the 2026 pilot."""
import argparse
import gzip
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

START = date(2026, 7, 30)
STOP = date(2026, 10, 28)  # exclusive
BIPAD = "https://bipadportal.gov.np/api/v1/river/"
WEATHER = "https://single-runs-api.open-meteo.com/v1/forecast"


def retrieve(url):
    for attempt in range(4):
        try:
            with urlopen(url, timeout=60) as response:
                return json.load(response)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


def download_day(task):
    day, folder = task
    cache = folder / (day.isoformat() + ".json.gz")
    if cache.exists():
        with gzip.open(cache, "rt") as source:
            return json.load(source)

    # Explicit offsets avoid interpreting a reporting day in the server's time zone.
    start = pd.Timestamp(day, tz="UTC")
    end = start + pd.Timedelta(days=1)
    query = dict(station=25, water_level_on__gt=(start - pd.Timedelta(seconds=1)).isoformat(),
                 water_level_on__lt=end.isoformat(), limit=500, ordering="id")
    observations = []
    offset = 0
    while True:
        response = retrieve(BIPAD + "?" + urlencode(dict(query, offset=offset)))
        records = response["results"]
        if not records:
            break
        for row in records:
            stamp = pd.Timestamp(row["waterLevelOn"])
            if row["stationSeriesId"] != 4140 or not start <= stamp < end:
                raise ValueError(f"Unexpected gauge record on {day}")
            # Modified records can only be used once the recorded version exists.
            observations.append([row["waterLevelOn"], max(pd.Timestamp(row["createdOn"]),
                                 pd.Timestamp(row["modifiedOn"]), stamp).isoformat(), row["waterLevel"]])
        if len(records) < 500 or not response["next"]:
            break
        offset += len(records)

    run = day.isoformat() + "T00:00"
    query = dict(latitude="28.21,28.23,28.00", longitude="83.99,84.38,84.63",
                 run=run, models="gfs_global", hourly="precipitation", timezone="GMT",
                 forecast_hours=120)
    sites = retrieve(WEATHER + "?" + urlencode(query))
    if len(sites) != 3:
        raise ValueError(f"Incomplete set of rain points on {day}")
    rain = []
    expected_times = pd.date_range(start, periods=120, freq="h")
    for i, site in enumerate(sites):
        hourly = site["hourly"]
        if (site["utc_offset_seconds"] != 0 or site["hourly_units"]["precipitation"] != "mm"
                or not pd.DatetimeIndex(pd.to_datetime(hourly["time"], utc=True)).equals(expected_times)
                or len(hourly["precipitation"]) != 120):
            raise ValueError(f"Unexpected forecast cycle or units on {day}")
        rain.extend([start.isoformat(), valid, i, value] for valid, value in
                    zip(hourly["time"], hourly["precipitation"]))
    result = dict(gauge=observations, rain=rain)
    temp = cache.with_suffix(".tmp")
    with gzip.open(temp, "wt") as dest:
        json.dump(result, dest)
    temp.replace(cache)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/raw/gandak_inputs"))
    args = parser.parse_args()
    cache = args.output / "daily"
    cache.mkdir(parents=True, exist_ok=True)
    days = [START + timedelta(days=i) for i in range((STOP - START).days)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        daily = list(pool.map(download_day, ((d, cache) for d in days)))
    for key, columns in [("gauge", ["observed", "available", "level_m"]),
                         ("rain", ["run", "valid", "site", "mm"])]:
        frame = pd.DataFrame([r for item in daily for r in item[key]], columns=columns)
        frame.to_csv(args.output / f"{key}.csv", index=False)
        print(key, len(frame))


if __name__ == "__main__":
    main()
