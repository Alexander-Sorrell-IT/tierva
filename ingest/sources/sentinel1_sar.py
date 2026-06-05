"""Sentinel-1 SAR backscatter time series over an AOI polygon, via Microsoft
Planetary Computer (Copernicus mirror, NO auth required). PARCEL-CAPABLE (10-20 m).

Mirrors sentinel2.ndvi_timeseries in spirit: search -> per-scene read ->
spatial-mean over the polygon -> tidy DataFrame, cached to data_cache/.

Auth: NONE (Planetary Computer signs assets in-place at search time; the open
'sentinel-1-grd' collection needs no subscription).

WHY THIS DOES NOT USE odc.stac.load (the bug that produced all-NaN backscatter)
===============================================================================
Sentinel-1 GRD *measurement* assets ('vv','vh') on Planetary Computer are
Cloud-Optimized GeoTIFFs in **raw radar (range/azimuth) geometry**: when you
open one with rasterio it reports ``crs == None`` and pixel-coordinate bounds
``(0, H, W, 0)``. They are NOT georeferenced by an affine+CRS — they carry only
~210 **Ground Control Points** (GCPs, in EPSG:4326) describing where each pixel
lands on the ground. On top of that, the STAC items expose **no** ``proj:epsg``
/ ``proj:transform`` metadata for these assets.

odc.stac.load asked to reproject to ``crs='EPSG:4326'`` therefore had no source
CRS/transform to work from. Whether it can fall back to the embedded GCPs is
entirely a function of the local GDAL build/version/config — on the backtest
machine it could not, so EVERY tile read raised and was silently swallowed by
``fail_on_error=False`` ("Ignoring read failure while reading …iw-vv.tiff"),
leaving an all-zero/all-NaN cube.

Fix: read each signed asset **explicitly** with rasterio, wrapping it in a
``WarpedVRT`` that warps from the embedded GCPs into EPSG:4326. This applies the
GCPs deterministically (independent of odc.stac's georeferencing path and of
whether the STAC carries proj metadata), then a single windowed, down-sampled
read pulls just the polygon bbox at the requested coarse resolution (the COGs
carry overviews, so this never materialises the full 16779×25137 array).

Collection choice (researched against the live STAC):
  * 'sentinel-1-grd'  — OPEN. Signs cleanly with planetary_computer.sign_inplace,
                        no subscription. Assets 'vv','vh' are Level-1 GRD
                        amplitude (digital number, NOT calibrated sigma0).  ← used
  * 'sentinel-1-rtc'  — radiometrically-terrain-corrected sigma0, BUT the
                        collection carries  msft:requires_account = True , i.e.
                        it needs a Planetary Computer subscription. We do NOT use
                        it, to stay 100%% no-auth like the Sentinel-2 path.

C-band backscatter caveats (honest):
  * GRD values are uncalibrated amplitude DN. 10*log10() therefore yields a
    *relative* dB scale, not true sigma0. That is fine for a downstream z-score,
    which is invariant to multiplicative scale and additive offset (10*log10 vs
    20*log10 vs a calibration constant all give the SAME z-score). True sigma0 is
    exactly what the account-gated RTC product would buy — not needed for an anomaly.
  * The soil-moisture -> backscatter link is land-cover dependent and can
    weaken/invert under a dense canopy, and mixing ascending/descending orbits +
    varying incidence angles injects viewing-geometry noise. Treat SAR as a
    *corroborating* sensor downstream, never a sole trigger.

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/sar_loader.py. Only the raw,
geometry-parameterized `sar_timeseries` pull is kept; the drought-coded z-score
anomaly lives in tierva/kernel/climatology.py, and the demo harness was dropped.
NOT yet validated against live data in this repo.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import warnings
import numpy as np
import pandas as pd
import rasterio
import rioxarray  # noqa: F401  (registers .rio accessor; kept for env parity)
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from rasterio.enums import Resampling
from rasterio.errors import NotGeoreferencedWarning, RasterioIOError

from ..access.planetary_computer import search

COLLECTION = "sentinel-1-grd"  # OPEN / no-auth (RTC requires a subscription)

CACHE_DIR = Path(__file__).parents[2] / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# GDAL/CURL options for fast, robust reads of the remote signed COGs.
_GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_USE_HEAD="NO",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
    VSI_CACHE="TRUE",
)


def _cache_path(geom, start: str, end: str, resolution: float) -> Path:
    """Stable cache filename from the request (bounds+dates+resolution hash).
    sar_timeseries() takes no AOI name, so we hash the geometry bounds."""
    key = f"{geom.bounds}|{start}|{end}|{resolution}"
    h = hashlib.md5(key.encode()).hexdigest()[:10]
    return CACHE_DIR / f"sar_{h}.parquet"


def _read_asset_mean_db(href: str, bounds, resolution: float):
    """Read one signed S1-GRD measurement asset (raw radar geometry, GCP-only)
    and return the spatial-mean *relative dB* over the polygon bbox.

    Steps:
      1. open the COG (crs=None, pixel-coord bounds, ~210 GCPs in EPSG:4326),
      2. WarpedVRT it from those GCPs into EPSG:4326 (deterministic georeferencing),
      3. windowed + down-sampled read of just the bbox at ~`resolution` degrees,
      4. mask amplitude<=0 (nodata / log10 domain), convert 10*log10 → relative dB,
      5. nan-mean. Returns np.nan if nothing finite overlaps the polygon.
    """
    minx, miny, maxx, maxy = bounds
    out_w = max(1, int(round((maxx - minx) / resolution)))
    out_h = max(1, int(round((maxy - miny) / resolution)))
    with warnings.catch_warnings():
        # The source has no affine geotransform (only GCPs); GDAL warns about
        # that on open. It is expected here — we georeference via the GCPs below.
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(href) as src:
            gcps, gcp_crs = src.gcps
            if not gcps or gcp_crs is None:
                # No GCPs and no CRS → genuinely cannot place these pixels.
                return np.nan
            with WarpedVRT(
                src,
                src_crs=gcp_crs,        # tell GDAL the GCPs are lon/lat
                crs="EPSG:4326",
                resampling=Resampling.average,
            ) as vrt:
                # Window over the polygon bbox, clamped to the warped extent so
                # we never request pixels outside the (boundless-incapable) VRT.
                win = from_bounds(minx, miny, maxx, maxy, vrt.transform)
                win = win.intersection(Window(0, 0, vrt.width, vrt.height))
                if win.width < 1 or win.height < 1:
                    return np.nan  # bbox does not overlap this scene's footprint
                arr = vrt.read(
                    1,
                    window=win,
                    out_shape=(out_h, out_w),
                    resampling=Resampling.average,
                )
    lin = arr.astype("float32")
    lin = np.where(lin > 0, lin, np.nan)  # log10 needs strictly-positive amplitude
    if not np.isfinite(lin).any():
        return np.nan
    db = 10.0 * np.log10(lin)             # relative dB (z-score makes the scale moot)
    return float(np.nanmean(db))


def sar_timeseries(
    geom,                        # shapely polygon in EPSG:4326
    start: str,                  # "2022-01-01"
    end: str,                    # "2024-12-31"
    resolution: float = 0.0018,  # ~200 m in degrees — coarse for speed (SAR is fine-res)
) -> pd.DataFrame:
    """Return DataFrame[date, vv_db, vh_db] of per-scene spatial-mean Sentinel-1
    GRD backscatter (relative dB) over the polygon. VH is NaN for VV-only
    (single-pol) scenes. Same-solar-day scenes are averaged together.
    Cached to data_cache/ keyed on (bounds, start, end, resolution)."""
    cache = _cache_path(geom, start, end, resolution)
    cols = ["date", "vv_db", "vh_db"]
    if cache.exists():
        return pd.read_parquet(cache)

    items = search(
        collections=[COLLECTION],
        geom=geom,
        datetime=f"{start}/{end}",
        # IW is the standard land-acquisition mode; excludes EW/strip-map so the
        # series isn't contaminated by a different acquisition geometry.
        query={"sar:instrument_mode": {"eq": "IW"}},
    )
    if not items:
        return pd.DataFrame(columns=cols)

    bounds = geom.bounds
    # Read every scene's VV (and VH where present), grouped by solar day so that
    # two consecutive frames of the same overpass collapse to one observation.
    per_day: dict = {}
    with rasterio.Env(**_GDAL_ENV):
        for it in items:
            day = pd.Timestamp(it.datetime).date()
            assets = it.assets
            if "vv" not in assets:
                continue  # VV is the channel we anomaly on; skip HH/HV-only frames
            try:
                vv = _read_asset_mean_db(assets["vv"].href, bounds, resolution)
            except (RasterioIOError, rasterio.errors.RasterioError, RuntimeError):
                vv = np.nan
            vh = np.nan
            if "vh" in assets:
                try:
                    vh = _read_asset_mean_db(assets["vh"].href, bounds, resolution)
                except (RasterioIOError, rasterio.errors.RasterioError, RuntimeError):
                    vh = np.nan
            slot = per_day.setdefault(day, {"vv": [], "vh": []})
            if np.isfinite(vv):
                slot["vv"].append(vv)
            if np.isfinite(vh):
                slot["vh"].append(vh)

    rows = []
    for day in sorted(per_day):
        vv_list = per_day[day]["vv"]
        if not vv_list:
            continue  # no usable VV over the polygon for this overpass
        vh_list = per_day[day]["vh"]
        rows.append({
            "date": day,
            "vv_db": float(np.mean(vv_list)),
            "vh_db": float(np.mean(vh_list)) if vh_list else np.nan,
        })

    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
        df.to_parquet(cache)
    return df
