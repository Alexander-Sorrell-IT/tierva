"""Climatology + z-score anomaly — domain-agnostic.

Turns a raw observation series into a standardized anomaly versus a multi-year
monthly baseline: the per-month "normal" (mean/std) computed from baseline
years, then z = (value - clim_mean) / clim_std for every row.

Lifted from Pacto Seco's drought DCSI (ndvi_anomaly) and generalized: nothing
here is named 'ndvi'. The caller names the value column and the output column,
so the same math drives a drought greenness index, a flood water-level index, a
heat anomaly, an air-quality signal — any monthly-seasonal Earth-observation
variable.

This module is pure pandas/numpy and is offline unit-testable (no I/O).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def monthly_climatology(
    df: pd.DataFrame,
    value_col: str,
    baseline_years,
    date_col: str = "date",
) -> pd.DataFrame:
    """Per-month mean & std from baseline years -> the 'normal' to compare against.

    NOTE: months that appear in the data but are absent from the baseline (no
    coverage), or that have <2 baseline obs (pandas std with ddof=1 -> NaN),
    will silently produce NaN anomalies downstream. We log a warning for those
    months rather than raising, so the caller can decide what to do.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["month"] = df[date_col].dt.month
    df["year"] = df[date_col].dt.year
    base = df[df["year"].isin(baseline_years)]
    clim = base.groupby("month")[value_col].agg(["mean", "std"]).rename(
        columns={"mean": "clim_mean", "std": "clim_std"})

    # Warn about months present in the data but lacking usable climatology.
    months_in_data = set(df["month"].dropna().unique())
    missing_month = sorted(months_in_data - set(clim.index))
    if missing_month:
        logger.warning(
            "%s climatology missing for months present in data: %s "
            "(no baseline coverage -> anomalies will be NaN)",
            value_col, missing_month,
        )
    # Months with too few baseline obs to compute a std (ddof=1 needs >=2).
    nan_std_months = sorted(
        m for m in clim.index
        if m in months_in_data and pd.isna(clim.loc[m, "clim_std"])
    )
    if nan_std_months:
        logger.warning(
            "%s climatology has NaN std (<2 baseline obs) for months: %s "
            "(anomalies will be NaN)",
            value_col, nan_std_months,
        )
    return clim


def zscore_anomaly(
    df: pd.DataFrame,
    value_col: str,
    baseline_years,
    out_col: str | None = None,
    date_col: str = "date",
) -> pd.DataFrame:
    """Add a z-score anomaly column: (value - clim_mean) / clim_std.

    Generic replacement for Pacto Seco's ndvi_anomaly. The sign convention is
    whatever the variable implies: for greenness, negative = stress; for water
    level or temperature, positive = above normal. The kernel's trigger
    `direction` param decides which tail breaches.

    Parameters
    ----------
    df : DataFrame with at least `date_col` and `value_col`.
    value_col : the raw observation column (e.g. "ndvi_mean", "water_level").
    baseline_years : iterable of years that define the climatological normal.
    out_col : name of the anomaly column to write. Defaults to
        f"{value_col}_anomaly".
    date_col : name of the date column. Defaults to "date".

    Returns the dataframe with `month`, `clim_mean`, `clim_std`, and the
    anomaly column joined on month.
    """
    out_col = out_col or f"{value_col}_anomaly"
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["month"] = df[date_col].dt.month
    clim = monthly_climatology(df, value_col, baseline_years, date_col=date_col)
    df = df.join(clim, on="month")
    # guard against zero std (a constant baseline month) -> NaN, not inf.
    df["clim_std"] = df["clim_std"].replace(0, np.nan)
    df[out_col] = (df[value_col] - df["clim_mean"]) / df["clim_std"]
    return df
