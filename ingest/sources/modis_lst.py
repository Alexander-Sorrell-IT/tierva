"""MODIS Land Surface Temperature loader — a POLAR-ORBITING thermal sensor.
REGION-ONLY CONTEXT (1 km).

MODIS/Aqua 8-day daytime Land Surface Temperature (MYD11A2, 1 km), pulled from
the FREE, no-auth Microsoft Planetary Computer STAC (same mirror the Sentinel-2
NDVI loader uses — NO key, NO login). A real agricultural drought dries and bakes
the land surface, so daytime LAND SURFACE TEMPERATURE RISES.

Auth: NONE (Planetary Computer signs assets in-place at search time).

PRODUCT / SOURCE (verified no-auth, mirrors sentinel2.py exactly):
  search(collections=['modis-11A2-061'], geom=..., datetime=...)
  -> odc.stac.load(items, bands=['LST_Day_1km'], bbox=..., crs='EPSG:4326')
  -> per-scene area-mean over the AOI bbox.
  Asset 'LST_Day_1km' verified on the STAC item-assets: 8-day daytime 1 km LST,
  raster:bands scale = 0.02, unit = Kelvin, data_type = uint16 (fill = 0).

WHY MODIS/AQUA ONLY (MYD11A2), NOT TERRA AND NOT BOTH MIXED
-----------------------------------------------------------
The collection modis-11A2-061 carries BOTH platforms: MOD11A2 (Terra, ~10:30
local daytime overpass) and MYD11A2 (Aqua, ~13:30 local). LST has a large diurnal
cycle, so MIXING the two platforms into one monthly mean reintroduces an
overpass/sampling-shift confound: if the per-month Terra/Aqua ratio differs
between a baseline year and the test year, that alone manufactures (or destroys) a
z-score signal. So we use ONE platform consistently across the baseline AND the
test year. We pick AQUA (MYD11A2) because its ~13:30 local daytime overpass sits
nearest the early-afternoon LST peak — where drought heat (failed evaporative
cooling) is strongest. Terra-only is the fallback if Aqua coverage is ever thin.

NODATA / SCALING (mandatory order — mask fill BEFORE scaling)
-------------------------------------------------------------
LST_Day_1km is uint16 with fill value 0. odc.stac returns the RAW DN (it does NOT
auto-apply the 0.02 scale — verified: nonzero DN ~15000, not ~300 K). We must
(1) mask DN == 0 (fill) to NaN, (2) apply Kelvin = DN * 0.02, (3) clamp to a
physical land-surface range [250, 345] K as a final guard, THEN area-mean. A
single un-masked fill pixel is 0 K = -273 °C and would wreck the area-mean.

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/modis_lst_loader.py. Only the raw,
geometry-parameterized `lst_timeseries` pull is kept; the drought-coded
sign-flipped z-score anomaly lives in tierva/kernel/climatology.py, and the demo
harness was dropped. NOT yet validated against live data in this repo.
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

COLLECTION = "modis-11A2-061"            # MODIS LST 8-day, 1 km (Terra + Aqua)
PLATFORM_PREFIX = "MYD"                  # MYD11A2 = Aqua (~13:30 local, peak heat)
LST_BAND = "LST_Day_1km"                 # 8-day daytime 1 km LST
LST_SCALE = 0.02                         # DN * 0.02 -> Kelvin (from raster:bands)
# physical land-surface temperature guard (Kelvin); anything outside is fill/garbage
LST_K_MIN, LST_K_MAX = 250.0, 345.0      # ~ -23 .. +72 °C


def lst_timeseries(
    geom,                       # shapely polygon in EPSG:4326
    start: str,                 # "2019-01-01"
    end: str,                   # "2023-12-31"
    resolution: float = 0.009,  # ~1 km in degrees — matches the native LST grid
    platform_prefix: str = PLATFORM_PREFIX,
    name: str | None = None,    # AOI name -> stable parquet cache filename
) -> pd.DataFrame:
    """Per-scene area-mean DAYTIME LST (°C) over the AOI bbox.

    Returns DataFrame[date, lst_c, n_pix, valid_frac], one row per 8-day Aqua
    composite, sorted by date. No auth (Planetary Computer signs in-place).
    Cached to data_cache/ when `name` is given (the STAC pull is the slow step).

    Steps (mirrors sentinel2.ndvi_timeseries):
      search modis-11A2-061 intersecting geom over [start,end]
      -> keep only Aqua (MYD11A2) items for fixed-overpass consistency
      -> odc.stac.load LST_Day_1km, reproject to EPSG:4326 over the bbox
      -> mask fill (DN==0), scale 0.02 -> Kelvin, clamp to [250,345] K -> °C
      -> spatial mean per 8-day scene.
    """
    cache = None
    if name is not None:
        safe = name.replace(" ", "")
        cache = CACHE_DIR / f"modislst_{safe}_{start[:4]}_{end[:4]}_{platform_prefix}.parquet"
        if cache.exists():
            return pd.read_parquet(cache)

    items = search(
        collections=[COLLECTION],
        geom=geom,
        datetime=f"{start}/{end}",
    )
    # fixed-platform (fixed overpass hour) — see module docstring
    items = [it for it in items if it.id.startswith(platform_prefix)]
    if not items:
        return pd.DataFrame(columns=["date", "lst_c", "n_pix", "valid_frac"])

    minx, miny, maxx, maxy = geom.bounds
    ds = odc.stac.load(
        items,
        bands=[LST_BAND],
        bbox=[minx, miny, maxx, maxy],
        resolution=resolution,
        crs="EPSG:4326",            # reproject MODIS sinusoidal -> lat/lon
        chunks={},
        groupby="solar_day",        # collapse the (single) tile per 8-day period
        fail_on_error=False,        # skip unreadable COGs instead of crashing
    )

    dn = ds[LST_BAND].astype("float32")
    # MANDATORY ORDER: mask fill (DN==0) BEFORE scaling, else 0 K = -273°C wrecks
    # the area-mean.
    dn = dn.where(dn != 0)
    kelvin = dn * LST_SCALE
    # final physical guard against any residual garbage DN
    kelvin = kelvin.where((kelvin >= LST_K_MIN) & (kelvin <= LST_K_MAX))
    celsius = kelvin - 273.15

    rows = []
    for t in celsius.time.values:
        frame = celsius.sel(time=t)
        vals = frame.values.ravel()
        valid = np.isfinite(vals)
        if valid.sum() == 0:
            continue
        rows.append({
            "date": pd.Timestamp(t).date(),
            "lst_c": float(np.nanmean(vals)),
            "n_pix": int(valid.sum()),
            "valid_frac": float(valid.mean()),
        })
    df = pd.DataFrame(rows, columns=["date", "lst_c", "n_pix", "valid_frac"])
    df = df.sort_values("date").reset_index(drop=True)
    if cache is not None and not df.empty:
        df.to_parquet(cache)
    return df
