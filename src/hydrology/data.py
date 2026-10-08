"""Preserve source qualifiers; never interpolate targets or bridge missing days."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

CFS_TO_CMS = 0.028316846592


def parse_usgs(payload, site="01646500"):
    matches = [s for s in payload["value"]["timeSeries"]
               if any(c["value"] == site for c in s["sourceInfo"]["siteCode"])
               and any(c["value"] == "00060" for c in s["variable"]["variableCode"])]
    if len(matches) != 1:
        raise ValueError("Expected exactly one discharge time series")
    series = matches[0]
    if series["variable"]["unit"]["unitCode"] != "ft3/s":
        raise ValueError("Unexpected discharge unit; conversion must be reviewed")
    rows = []
    nodata = float(series["variable"].get("noDataValue", -999999))
    for block in series["values"]:
        for item in block["value"]:
            value = float(item["value"])
            flags = item.get("qualifiers", [])
            # Require USGS-approved values; retain estimated-value flags for audit.
            usable = np.isfinite(value) and value >= 0 and value != nodata and "A" in flags
            rows.append({"date": item["dateTime"][:10], "site_id": site,
                         "discharge_cfs": value if usable else np.nan,
                         "discharge_cms": value * CFS_TO_CMS if usable else np.nan,
                         "qualifiers": ";".join(flags), "usable": usable})
    frame = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if frame.empty or frame.date.duplicated().any():
        raise ValueError("Empty or duplicate-date streamflow response")
    return frame, series["sourceInfo"]["siteName"]


def make_windows(frame, lookback=30, train_end="2009-12-31",
                 validation_end="2014-12-31", calibration_end="2019-12-31"):
    if lookback < 1:
        raise ValueError("lookback must be positive")
    cutoffs = pd.to_datetime([train_end, validation_end, calibration_end])
    if not cutoffs.is_monotonic_increasing or cutoffs.duplicated().any():
        raise ValueError("Split dates must be strictly increasing")
    dates = pd.DatetimeIndex(pd.to_datetime(frame.date))
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Dates must be unique and increasing")
    q = frame.discharge_cms.to_numpy(dtype=float)
    if np.any(q[np.isfinite(q)] < 0):
        raise ValueError("Negative streamflow is unsupported by this benchmark")
    z = np.log1p(q)
    train_values = z[(dates <= cutoffs[0]) & np.isfinite(z)]
    if len(train_values) < 2:
        raise ValueError("Too few training observations")
    mean, scale = float(train_values.mean()), float(train_values.std())
    if scale < 1e-8:
        raise ValueError("Training series has no variation")
    phase = 2 * np.pi * (dates.dayofyear.to_numpy() - 1) / 365.2425
    features = np.column_stack(((z - mean) / scale, np.sin(phase), np.cos(phase)))
    windows, targets, indexes = [], [], []
    for t in range(lookback, len(frame)):
        # Forecast t from t-lookback ... t-1 only. Entire window must be daily.
        if (dates[t] - dates[t-lookback]).days != lookback:
            continue
        if not np.isfinite(z[t-lookback:t+1]).all():
            continue
        windows.append(features[t-lookback:t])
        targets.append((z[t] - mean) / scale)
        indexes.append(t)
    if not indexes:
        raise ValueError("No complete daily forecast windows")
    ids = np.asarray(indexes)
    target_dates = dates[ids]
    masks = {"train": target_dates <= cutoffs[0],
             "validation": (target_dates > cutoffs[0]) & (target_dates <= cutoffs[1]),
             "calibration": (target_dates > cutoffs[1]) & (target_dates <= cutoffs[2]),
             "test": target_dates > cutoffs[2]}
    if any(int(mask.sum()) < 2 for mask in masks.values()):
        raise ValueError("Each chronological partition needs at least two windows")
    return {"x": np.asarray(windows, dtype=np.float32),
            "y": np.asarray(targets, dtype=np.float32), "q": q[ids],
            "persistence": q[ids-1], "dates": target_dates,
            "masks": masks, "mean": mean, "scale": scale}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="01646500")
    parser.add_argument("--start", default="1990-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--raw", type=Path, default=Path("data/raw/usgs/01646500_daily_1990_2025.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/streamflow.csv"))
    parser.add_argument("--download", action="store_true", help="Fetch a new source response")
    args = parser.parse_args()
    url = "https://waterservices.usgs.gov/nwis/dv/?" + urlencode({
        "format": "json", "sites": args.site, "startDT": args.start, "endDT": args.end,
        "parameterCd": "00060", "statCd": "00003", "siteStatus": "all"})
    if args.download:
        with urlopen(Request(url, headers={"User-Agent": "HydrologyInstituteResearch/0.1"}), timeout=60) as response:
            raw = response.read()
        parse_usgs(json.loads(raw), args.site)  # Validate before saving.
        args.raw.parent.mkdir(parents=True, exist_ok=True)
        args.raw.write_bytes(raw)
    raw = args.raw.read_bytes()
    frame, name = parse_usgs(json.loads(raw), args.site)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    report = {"source_url": url, "site": args.site, "site_name": name,
              "raw_sha256": hashlib.sha256(raw).hexdigest(), "rows": len(frame),
              "usable_rows": int(frame.usable.sum()),
              "estimated_rows": int(frame.qualifiers.str.split(";").apply(lambda q: "e" in q).sum()),
              "start": frame.date.min(), "end": frame.date.max(),
              "conversion_cfs_to_cms": CFS_TO_CMS}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
