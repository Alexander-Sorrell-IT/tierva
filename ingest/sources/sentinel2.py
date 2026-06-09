"""Sentinel-2 NDVI time series over an AOI polygon, via Microsoft Planetary
Computer (Copernicus mirror, no auth required). PARCEL-CAPABLE (10 m, flagship).

NDVI = (B08 - B04) / (B08 + B04). Cloud-masked via the Scene Classification Layer
(SCL). Aggregated to a per-scene spatial-mean over the polygon -> a clean NDVI
time series.

Auth: NONE (Planetary Computer signs assets in-place at search time).

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/sentinel_loader.py. Only the raw,
geometry-parameterized `ndvi_timeseries` pull is kept here; the drought-coded
z-score anomaly lives in tierva/kernel/climatology.py, and the demo harness was
dropped. NOT yet validated against live data in this repo.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401  (registers .rio accessor)
import odc.stac

from ..access.planetary_computer import search

# SCL values that are NOT valid vegetation observation (cloud, shadow, snow, water, saturated)
SCL_BAD = {0, 1, 3, 6, 8, 9, 10, 11}


def ndvi_timeseries(
    geom,                       # shapely polygon in EPSG:4326
    start: str,                 # "2022-01-01"
    end: str,                   # "2024-12-31"
    max_cloud: int = 60,
    resolution: float = 0.0009, # ~100 m in degrees — coarse for speed
) -> pd.DataFrame:
    """Return DataFrame[date, ndvi_mean, ndvi_std, valid_frac] for the polygon."""
    items = search(
        collections=["sentinel-2-l2a"],
        geom=geom,
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    if not items:
        return pd.DataFrame(columns=["date", "ndvi_mean", "ndvi_std", "valid_frac"])

    minx, miny, maxx, maxy = geom.bounds
    ds = odc.stac.load(
        items,
        bands=["B04", "B08", "SCL"],
        bbox=[minx, miny, maxx, maxy],
        resolution=resolution,
        crs="EPSG:4326",
        chunks={},
        groupby="solar_day",
        fail_on_error=False,  # skip corrupt/unreadable COG tiles instead of crashing
    )

    red = ds["B04"].astype("float32")
    nir = ds["B08"].astype("float32")
    scl = ds["SCL"]
    good = ~scl.isin(list(SCL_BAD))

    # Mask BEFORE the division (mask-then-divide), matching ingest/parcel.py:
    #   * nodata is 0 on the reflectance bands -> drop non-positive pixels to NaN
    #     so they cannot reach the divide.
    #   * guard the denominator: where (nir+red) is ~0 the ratio is undefined, so
    #     NaN it out rather than letting inf/NaN survive the later .where(good).
    # Using xarray .where() (not np.where) preserves dims/coords on the DataArray.
    red = red.where(red > 0)
    nir = nir.where(nir > 0)
    denom = nir + red
    ndvi = (nir - red) / denom.where(denom != 0)
    ndvi = ndvi.where(good)

    # spatial-mean per time step
    rows = []
    for t in ndvi.time.values:
        frame = ndvi.sel(time=t)
        vals = frame.values.ravel()
        valid = np.isfinite(vals)
        if valid.sum() == 0:
            continue
        rows.append({
            "date": pd.Timestamp(t).date(),
            "ndvi_mean": float(np.nanmean(vals)),
            "ndvi_std": float(np.nanstd(vals)),
            "valid_frac": float(valid.mean()),
        })
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df
