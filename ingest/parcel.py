"""FAST parcel-readout engine — the data layer behind "see your land NOW".

`parcel_readout(lat, lon, buffer_m=250)` returns the LATEST clear, parcel-true
signals for ANY parcel on Earth, all no-auth via Microsoft Planetary Computer:

  * NDVI            — Sentinel-2 L2A, the latest scene that is actually clear
                      OVER THE PARCEL (SCL-validated, not just scene-level cloud).
  * radar dB        — Sentinel-1 GRD VV/VH backscatter (relative dB), the latest
                      IW scene whose footprint covers the parcel.
  * cropland flag   — ESA WorldCover (10 m); is this parcel cropland, and what
                      fraction of the parcel box is cropland.

WHY THIS IS FAST (the perf fix)
===============================
The existing `sentinel2.ndvi_timeseries` / `sentinel1_sar.sar_timeseries` pull a
whole time series: N scenes, each materialised (odc.stac) or windowed and then
spatial-meaned in a SEQUENTIAL Python loop (~4 s/scene). For a live "what does my
land look like NOW" readout you do not want a series — you want the single latest
clear value. So:

  1. Search each collection ONCE, sort newest-first.
  2. Read only the LATEST usable scene, with a SINGLE windowed (overview-backed)
     read over the small parcel box — never the full 10980x10980 array.
  3. Run the three sensors CONCURRENTLY (threads), and the three Sentinel-2 bands
     CONCURRENTLY within the S2 task. GDAL releases the GIL during reads and each
     `search()` opens its own catalog, so this is thread-safe.

The dominant wall-clock cost is the STAC search (~8 s each), so sensor-level
concurrency — three searches at once instead of in series — is the single biggest
lever, bigger than threading the bands. The READ itself (the thing the old loop
did N times at ~4 s each) is now one small windowed read, a few hundred ms.

Auth: NONE. Planetary Computer signs asset hrefs in-place at search time.
"""
from __future__ import annotations

import math
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import NotGeoreferencedWarning, RasterioIOError
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

from .access.planetary_computer import search
from .sources.sentinel2 import SCL_BAD
from .sources.sentinel1_sar import _read_asset_mean_db
from .sources.worldcover_cropland import (
    CROPLAND_CLASS,
    WORLDCOVER_COLLECTION,
    WORLDCOVER_MAP_BAND,
)

# GDAL/CURL options for fast, robust reads of the remote signed COGs
# (same set the S1 loader uses).
_GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_USE_HEAD="NO",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
    VSI_CACHE="TRUE",
)

# How clear the parcel must be (fraction of SCL pixels that are valid vegetation
# observation) before we accept a Sentinel-2 scene for the live NDVI readout.
_MIN_VALID_FRAC = 0.5
# How many newest-first scenes to try before giving up on a clear NDVI / finite SAR.
_MAX_SCENE_TRIES = 3


def _parcel_box(lat: float, lon: float, buffer_m: float):
    """Square parcel box (shapely) of half-width `buffer_m`, lat-corrected.

    meters -> degrees: dlat = m / 110540 ; dlon = m / (111320 * cos(lat)).
    """
    dlat = buffer_m / 110540.0
    dlon = buffer_m / (111320.0 * max(0.01, math.cos(math.radians(lat))))
    return box(lon - dlon, lat - dlat, lon + dlon, lat + dlat)


# --------------------------------------------------------------------------- #
# Sentinel-2: latest scene that is clear OVER THE PARCEL.                      #
# --------------------------------------------------------------------------- #
def _read_band_window(href: str, bounds4326, out_shape, resampling):
    """Single windowed, overview-backed read of one georeferenced S2 COG over the
    parcel bbox, resampled to a common `out_shape`. Returns a float32 array (or
    None if the parcel does not overlap the scene)."""
    minx, miny, maxx, maxy = bounds4326
    out_h, out_w = out_shape
    with rasterio.open(href) as src:
        dst_bounds = transform_bounds("EPSG:4326", src.crs, minx, miny, maxx, maxy)
        win = from_bounds(*dst_bounds, src.transform)
        win = win.intersection(Window(0, 0, src.width, src.height))
        if win.width < 1 or win.height < 1:
            return None
        arr = src.read(
            1,
            window=win,
            out_shape=(out_h, out_w),
            resampling=resampling,
        )
    return arr.astype("float32")


def _ndvi_from_scene(item, bounds4326, out_shape):
    """Read B04/B08/SCL of one S2 item CONCURRENTLY over the parcel and return
    (ndvi_mean, valid_frac) restricted to SCL-valid pixels, or (nan, 0.0)."""
    a = item.assets
    with rasterio.Env(**_GDAL_ENV):
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_red = ex.submit(_read_band_window, a["B04"].href, bounds4326, out_shape, Resampling.average)
            f_nir = ex.submit(_read_band_window, a["B08"].href, bounds4326, out_shape, Resampling.average)
            # SCL is categorical (20 m) -> nearest, never average.
            f_scl = ex.submit(_read_band_window, a["SCL"].href, bounds4326, out_shape, Resampling.nearest)
            red, nir, scl = f_red.result(), f_nir.result(), f_scl.result()
    if red is None or nir is None or scl is None:
        return float("nan"), 0.0

    # nodata=0 on the reflectance bands; mask before NDVI.
    red = np.where(red > 0, red, np.nan)
    nir = np.where(nir > 0, nir, np.nan)
    good = ~np.isin(scl.astype("int16"), list(SCL_BAD))

    ndvi = (nir - red) / (nir + red)
    ndvi = np.where(good, ndvi, np.nan)
    valid = np.isfinite(ndvi)
    valid_frac = float(valid.mean()) if valid.size else 0.0
    if valid.sum() == 0:
        return float("nan"), valid_frac
    return float(np.nanmean(ndvi)), valid_frac


def _sentinel2_readout(parcel, start: str, end: str, out_shape):
    """Latest Sentinel-2 scene that is clear over the parcel."""
    items = search(
        collections=["sentinel-2-l2a"],
        geom=parcel,
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": 60}},
    )
    out = {"ndvi": None, "ndvi_date": None, "valid_frac": None,
           "scene_cloud": None, "n_scenes": len(items), "tried": 0}
    if not items:
        return out

    items = sorted(items, key=lambda x: x.datetime, reverse=True)
    bounds = parcel.bounds
    best = None  # fallback: highest valid_frac seen even if below threshold
    for it in items[:_MAX_SCENE_TRIES]:
        out["tried"] += 1
        ndvi, vf = _ndvi_from_scene(it, bounds, out_shape)
        cand = {
            "ndvi": ndvi, "valid_frac": vf,
            "ndvi_date": it.datetime.date().isoformat(),
            "scene_cloud": it.properties.get("eo:cloud_cover"),
        }
        if best is None or (vf > (best["valid_frac"] or 0.0)):
            best = cand
        if np.isfinite(ndvi) and vf >= _MIN_VALID_FRAC:
            out.update(cand)
            return out
    if best is not None:
        out.update(best)  # nothing crossed threshold -> return the clearest we saw
    return out


# --------------------------------------------------------------------------- #
# Sentinel-1: latest IW scene covering the parcel (relative dB).               #
# --------------------------------------------------------------------------- #
def _sentinel1_readout(parcel, start: str, end: str, resolution: float):
    """Latest Sentinel-1 GRD IW scene whose footprint covers the parcel.

    Reuses sentinel1_sar._read_asset_mean_db (GCP -> WarpedVRT -> windowed read,
    relative dB). Iterates newest-first until VV reads finite (footprint overlap)."""
    items = search(
        collections=["sentinel-1-grd"],
        geom=parcel,
        datetime=f"{start}/{end}",
        query={"sar:instrument_mode": {"eq": "IW"}},
    )
    out = {"vv_db": None, "vh_db": None, "sar_date": None, "n_scenes": len(items), "tried": 0}
    if not items:
        return out

    items = sorted(items, key=lambda x: x.datetime, reverse=True)
    bounds = parcel.bounds
    with rasterio.Env(**_GDAL_ENV):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            for it in items[:_MAX_SCENE_TRIES]:
                a = it.assets
                if "vv" not in a:
                    continue
                out["tried"] += 1
                try:
                    vv = _read_asset_mean_db(a["vv"].href, bounds, resolution)
                except (RasterioIOError, rasterio.errors.RasterioError, RuntimeError):
                    vv = float("nan")
                if not np.isfinite(vv):
                    continue
                vh = float("nan")
                if "vh" in a:
                    try:
                        vh = _read_asset_mean_db(a["vh"].href, bounds, resolution)
                    except (RasterioIOError, rasterio.errors.RasterioError, RuntimeError):
                        vh = float("nan")
                out.update({
                    "vv_db": float(vv),
                    "vh_db": float(vh) if np.isfinite(vh) else None,
                    "sar_date": it.datetime.date().isoformat(),
                })
                return out
    return out


# --------------------------------------------------------------------------- #
# WorldCover: is this parcel cropland?                                         #
# --------------------------------------------------------------------------- #
def _worldcover_readout(parcel, resolution: float):
    """Cropland flag + cropland fraction over the parcel via ESA WorldCover.

    Single windowed read of the latest WorldCover `map` COG (10 m, georeferenced),
    rather than odc.stac materialisation, to stay fast and consistent with the
    other two paths."""
    bounds = parcel.bounds
    items = search(collections=[WORLDCOVER_COLLECTION], bbox=list(bounds))
    out = {"cropland": None, "cropland_frac": None, "dominant_class": None,
           "wc_year": None, "n_scenes": len(items)}
    if not items:
        return out

    # Latest map version (2021 v200 after 2020 v100). WorldCover items carry an
    # interval (start_datetime/end_datetime), so item.datetime is often None —
    # sort on whatever date field is present, newest last.
    def _wc_key(x):
        d = x.datetime or x.properties.get("end_datetime") or x.properties.get("start_datetime") or ""
        return str(d)
    it = sorted(items, key=_wc_key, reverse=True)[0]
    out["wc_year"] = _wc_key(it)[:10] or None
    href = it.assets[WORLDCOVER_MAP_BAND].href
    minx, miny, maxx, maxy = bounds
    out_w = max(1, int(round((maxx - minx) / resolution)))
    out_h = max(1, int(round((maxy - miny) / resolution)))
    with rasterio.Env(**_GDAL_ENV):
        with rasterio.open(href) as src:
            # WorldCover is in EPSG:4326 already, but transform_bounds is a no-op-safe
            # way to be CRS-agnostic.
            dst_bounds = transform_bounds("EPSG:4326", src.crs, minx, miny, maxx, maxy)
            win = from_bounds(*dst_bounds, src.transform)
            win = win.intersection(Window(0, 0, src.width, src.height))
            if win.width < 1 or win.height < 1:
                return out
            arr = src.read(1, window=win, out_shape=(out_h, out_w),
                           resampling=Resampling.nearest)
    flat = arr.ravel()
    flat = flat[flat != 0]  # 0 = WorldCover nodata
    if flat.size == 0:
        return out
    crop = int((flat == CROPLAND_CLASS).sum())
    out["cropland_frac"] = float(crop / flat.size)
    out["cropland"] = bool(out["cropland_frac"] >= 0.5)
    vals, counts = np.unique(flat, return_counts=True)
    out["dominant_class"] = int(vals[int(np.argmax(counts))])
    return out


# --------------------------------------------------------------------------- #
# Public entry point.                                                          #
# --------------------------------------------------------------------------- #
@dataclass
class ParcelReadout:
    lat: float
    lon: float
    buffer_m: float
    bbox: tuple
    # Sentinel-2 NDVI (latest scene clear over the parcel)
    ndvi: float | None = None
    ndvi_date: str | None = None
    ndvi_valid_frac: float | None = None
    ndvi_scene_cloud: float | None = None
    # Sentinel-1 SAR (relative dB, latest IW scene)
    vv_db: float | None = None
    vh_db: float | None = None
    sar_date: str | None = None
    # ESA WorldCover cropland
    cropland: bool | None = None
    cropland_frac: float | None = None
    dominant_landcover: int | None = None
    worldcover_year: str | None = None
    # provenance / timing
    seconds: float | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def parcel_readout(
    lat: float,
    lon: float,
    buffer_m: float = 250,
    days: int = 45,
    end: str | None = None,
    s2_out_px: int = 24,
    s1_resolution: float = 0.0018,
    wc_resolution: float = 0.0001,
) -> ParcelReadout:
    """Latest clear, parcel-true signals for the parcel at (lat, lon).

    Parameters
    ----------
    lat, lon   : parcel centre, EPSG:4326 degrees.
    buffer_m   : half-width of the square parcel box, metres (default 250 -> 500 m box).
    days       : lookback window for S2/S1 (default 45). Widened once if empty.
    end        : window end "YYYY-MM-DD" (default: today).
    s2_out_px  : common pixel side the 3 S2 bands are resampled to (alignment).
    s1_resolution / wc_resolution : read grid spacing in degrees.

    Returns a ParcelReadout (dataclass; .to_dict() for JSON). Runs the three
    sensors concurrently; wall-clock recorded in `.seconds`.
    """
    import datetime as _dt

    t0 = time.time()
    if end is None:
        end = _dt.date.today().isoformat()
    end_d = _dt.date.fromisoformat(end)

    parcel = _parcel_box(lat, lon, buffer_m)
    out_shape = (s2_out_px, s2_out_px)

    def _window(d):
        start = (end_d - _dt.timedelta(days=d)).isoformat()
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_s2 = ex.submit(_sentinel2_readout, parcel, start, end, out_shape)
            f_s1 = ex.submit(_sentinel1_readout, parcel, start, end, s1_resolution)
            f_wc = ex.submit(_worldcover_readout, parcel, wc_resolution)
            return f_s2.result(), f_s1.result(), f_wc.result()

    s2, s1, wc = _window(days)
    # Widen once if both time-series sensors found nothing (short window in a
    # cloudy/low-revisit period).
    if (s2["n_scenes"] == 0 and s1["n_scenes"] == 0) and days < 90:
        s2, s1, _wc2 = _window(90)

    r = ParcelReadout(
        lat=lat, lon=lon, buffer_m=buffer_m, bbox=tuple(round(c, 6) for c in parcel.bounds),
        ndvi=(s2["ndvi"] if s2["ndvi"] is not None and np.isfinite(s2["ndvi"]) else None),
        ndvi_date=s2["ndvi_date"],
        ndvi_valid_frac=s2["valid_frac"],
        ndvi_scene_cloud=s2["scene_cloud"],
        vv_db=s1["vv_db"],
        vh_db=s1["vh_db"],
        sar_date=s1["sar_date"],
        cropland=wc["cropland"],
        cropland_frac=wc["cropland_frac"],
        dominant_landcover=wc["dominant_class"],
        worldcover_year=wc["wc_year"],
        seconds=round(time.time() - t0, 2),
        detail={"s2": s2, "s1": s1, "worldcover": wc, "lookback_days": days},
    )
    return r


if __name__ == "__main__":
    import json
    for nm, (la, lo) in {
        "california_central_valley": (36.60, -119.70),
        "france_farm": (48.80, 1.90),
    }.items():
        r = parcel_readout(la, lo)
        print(f"\n=== {nm} ({la},{lo}) ===")
        print(json.dumps(r.to_dict(), indent=2, default=str))
