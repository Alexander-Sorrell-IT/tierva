"""MODIS Vegetation Indices loader — an INDEPENDENT greenness cross-check on
Sentinel-2. FIELD-TO-REGION (250 m).

A CREDIBILITY CHECK on the Sentinel-2 NDVI signal. MODIS (NASA, Terra+Aqua, 250 m,
a completely different sensor, orbit, atmospheric correction and compositing
algorithm) gives an entirely independent measurement of the SAME physical quantity
— canopy greenness. If MODIS NDVI moves the same way Sentinel-2 NDVI does, the
greenness signal is sensor-robust, not an artifact of one processing chain.

Auth: NONE (Planetary Computer signs assets in-place at search time).

PRODUCT / SOURCE (verified no-auth, mirrors sentinel2.py / modis_lst.py):
  search(collections=['modis-13Q1-061'], geom=..., datetime=...)
  -> odc.stac.load(items, bands=['250m_16_days_NDVI'], bbox=..., crs='EPSG:4326')
  -> per-scene area-mean over the AOI bbox.
  Asset '250m_16_days_NDVI' verified on the STAC item-assets:
    16-day NDVI, 250 m, raster:bands scale = 0.0001, unit = NDVI, data_type = int16.
  Collection = MODIS Vegetation Indices 16-Day (250m). NO key, NO login.

TERRA + AQUA, BOTH KEPT (unlike the LST loader)
-----------------------------------------------
modis-13Q1-061 carries BOTH MOD13Q1 (Terra) and MYD13Q1 (Aqua). The LST loader
deliberately used Aqua ONLY because LST has a huge diurnal cycle and the two
platforms overpass at different local hours. NDVI has NO such problem: the 16-day
product is an atmospherically corrected, BRDF-/cloud-screened MAXIMUM-VALUE
composite that is by construction near-insensitive to overpass time. Terra and
Aqua are phase-staggered by 8 days, so keeping BOTH gives ~8-day effective NDVI
sampling — strictly better temporal coverage with no confound. We keep both,
applied identically across baseline and test years.

NODATA / SCALING (mandatory order — mask fill BEFORE scaling; verified empirically)
-----------------------------------------------------------------------------------
250m_16_days_NDVI is int16. odc.stac returns the RAW DN; it does NOT auto-apply
the 0.0001 scale (verified: raw DN range = -3000 .. 9990, NOT -0.3 .. 1.0). The
MODIS VI fill value is -3000 and the valid range is [-2000, 10000]. We therefore
(1) mask DN == -3000 (fill) to NaN, (2) clamp to the valid DN range [-2000, 10000]
as a guard, (3) apply NDVI = DN * 0.0001, THEN area-mean. A single un-masked -3000
fill pixel scales to NDVI = -0.3 and would fake a browning signal in the area-mean.

NOTE on the 'pixel_reliability' QA band: it is int8 with nodata = 255, which
overflows int8 and CRASHES odc.stac (OverflowError) — so we cannot load it via odc
here. We do not need it: the 16-day VI product is already cloud-/quality-composited
at source (observed valid_frac ~= 1.0 over a typical AOI), so fill + valid-range
masking is sufficient and is applied identically to every scene in every year.

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/modis_vi_loader.py. Only the raw,
geometry-parameterized `modis_ndvi_timeseries` pull is kept; the drought-coded
z-score anomaly lives in tierva/kernel/climatology.py, and the demo harness was
dropped. NOT yet validated against live data in this repo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401  (registers .rio accessor)
import odc.stac

from ..access.planetary_computer import search

CACHE_DIR = Path(__file__).parents[2] / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION = "modis-13Q1-061"           # MODIS Vegetation Indices 16-day, 250 m
NDVI_BAND = "250m_16_days_NDVI"         # 16-day NDVI
NDVI_SCALE = 0.0001                     # DN * 0.0001 -> NDVI (from raster:bands)
NDVI_FILL = -3000                       # MODIS VI fill value
NDVI_DN_MIN, NDVI_DN_MAX = -2000, 10000  # valid DN range (-> NDVI in [-0.2, 1.0])


def modis_ndvi_timeseries(
    geom,                       # shapely polygon in EPSG:4326
    start: str,                 # "2019-01-01"
    end: str,                   # "2023-12-31"
    resolution: float = 0.0025,  # ~250 m in degrees — matches the native VI grid
    name: str | None = None,    # AOI name -> stable parquet cache filename
) -> pd.DataFrame:
    """Per-scene area-mean NDVI over the AOI bbox (Terra + Aqua, 16-day).

    Returns DataFrame[date, ndvi_mean, ndvi_std, n_pix, valid_frac], one row per
    16-day composite (Terra and Aqua phase-staggered -> ~8-day effective spacing),
    sorted by date. No auth (Planetary Computer signs in-place). Cached to
    data_cache/ when `name` is given (the STAC pull is the slow step).

    NOTE: the per-scene column is named 'ndvi_mean' to match sentinel2's output
    schema, so the same downstream NDVI anomaly could be applied if desired.

    Steps (mirrors sentinel2.ndvi_timeseries / modis_lst.lst_timeseries):
      search modis-13Q1-061 intersecting geom over [start,end]
      -> odc.stac.load 250m_16_days_NDVI, reproject sinusoidal -> EPSG:4326 over bbox
      -> mask fill (DN==-3000), clamp valid DN range, scale 0.0001 -> NDVI
      -> spatial mean per 16-day scene.
    """
    cache = None
    if name is not None:
        safe = name.replace(" ", "")
        cache = CACHE_DIR / f"modisndvi_{safe}_{start[:4]}_{end[:4]}.parquet"
        if cache.exists():
            return pd.read_parquet(cache)

    items = search(
        collections=[COLLECTION],
        geom=geom,
        datetime=f"{start}/{end}",
    )  # keep BOTH Terra (MOD) and Aqua (MYD) — see docstring
    if not items:
        return pd.DataFrame(
            columns=["date", "ndvi_mean", "ndvi_std", "n_pix", "valid_frac"])

    minx, miny, maxx, maxy = geom.bounds
    ds = odc.stac.load(
        items,
        bands=[NDVI_BAND],          # NOT pixel_reliability (int8/255 nodata crashes odc)
        bbox=[minx, miny, maxx, maxy],
        resolution=resolution,
        crs="EPSG:4326",            # reproject MODIS sinusoidal -> lat/lon
        chunks={},
        groupby="solar_day",        # collapse tiles per composite date
        fail_on_error=False,        # skip unreadable COGs instead of crashing
    )

    dn = ds[NDVI_BAND].astype("float32")
    # MANDATORY ORDER: mask fill (DN==-3000) and clamp valid range BEFORE scaling,
    # else a -3000 fill pixel scales to NDVI=-0.3 and fakes a browning area-mean.
    dn = dn.where(dn != NDVI_FILL)
    dn = dn.where((dn >= NDVI_DN_MIN) & (dn <= NDVI_DN_MAX))
    ndvi = dn * NDVI_SCALE

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
            "n_pix": int(valid.sum()),
            "valid_frac": float(valid.mean()),
        })
    df = pd.DataFrame(
        rows, columns=["date", "ndvi_mean", "ndvi_std", "n_pix", "valid_frac"])
    df = df.sort_values("date").reset_index(drop=True)
    if cache is not None and not df.empty:
        df.to_parquet(cache)
    return df
