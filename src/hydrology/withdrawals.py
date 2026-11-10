"""USGS withdrawal reconstruction and seasonal demand forecasting."""
import numpy as np
import pandas as pd

CFS_TO_M3_DAY = 0.028316846592 * 86400


def demand_records(forecasts, raw):
    rows = [line.rstrip().split("\t") for line in raw.read_text().splitlines() if line.startswith("USGS\t")]
    data = pd.DataFrame(rows, columns=["agency","site","date","cfs","status"])
    flows = data.pivot(index="date", columns="site", values="cfs").astype(float)
    status = data.pivot(index="date", columns="site", values="status")
    table = pd.DataFrame(index=pd.Index(forecasts.date, name="date"))
    table["unadjusted_cfs"] = flows["01646500"]
    table["adjusted_cfs"] = flows["01646502"]
    table["unadjusted_status"] = status["01646500"]
    table["adjusted_status"] = status["01646502"]
    table["diversion_m3_day"] = (table.adjusted_cfs - table.unadjusted_cfs) * CFS_TO_M3_DAY
    approved = {"A", "A:R"}
    table["quality"] = np.select([
        table.diversion_m3_day.isna(),
        ~table.adjusted_status.isin(approved) | ~table.unadjusted_status.isin(approved),
        table.diversion_m3_day.le(0)],
        ["missing","estimated_or_provisional","nonpositive_difference"], default="included")
    return table.reset_index()


def calendar(dates):
    dates = pd.DatetimeIndex(dates)
    # The calendar is known in advance, including leap years and weekdays.
    phase = 2 * np.pi * (dates.dayofyear - 1) / np.where(dates.is_leap_year, 366, 365)
    columns = [np.ones(len(dates))]
    for harmonic in (1, 2):
        columns.extend([np.sin(harmonic*phase), np.cos(harmonic*phase)])
    columns.extend(dates.dayofweek == weekday for weekday in range(1, 7))
    return np.column_stack(columns)


def fit_calendar(demand, cutoff):
    train = demand.loc[:cutoff].dropna()
    if train.index.has_duplicates or len(train) < 365:
        raise ValueError("Need at least one year of unique daily withdrawals")
    coef, _, rank, _ = np.linalg.lstsq(calendar(train.index), train.to_numpy(), rcond=None)
    if rank != len(coef):
        raise ValueError("Insufficient coverage of calendar features")
    return coef, train.mean(), len(train)


def forecast(dates, coefficients):
    return np.maximum(calendar(dates) @ coefficients, 0.)
