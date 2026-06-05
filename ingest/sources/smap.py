"""SMAP soil-moisture time series over an AOI bbox — the *direct* soil-water
sensor. REGION-ONLY CONTEXT (~9 km).

Mirrors the Earthdata access pattern (CMR granule search -> bearer-auth download
-> per-granule read -> spatial-mean over the bbox -> tidy DataFrame), cached to
data_cache/.

PRODUCT CHOICE — SPL4SMGP (L4, root-zone, 9 km, native 3-hourly -> daily mean)
==============================================================================
Two candidates were considered:

  * SPL3SMP_E  — L3 *enhanced* radiometer, 9 km, daily. SURFACE soil moisture
                 only (top ~5 cm). Good, but the top 5 cm dries and re-wets with
                 every passing shower; for AGRICULTURAL drought it is the noisy
                 layer (a single rain day can mask a multi-week root-zone deficit).
  * SPL4SMGP   — L4 model-assimilation product, 9 km, 3-hourly. Provides BOTH
                 'sm_surface' AND 'sm_rootzone' (0–100 cm). ← CHOSEN.

We pick **SPL4SMGP** and read **sm_rootzone** because the crop-relevant water
store is the root zone, not the skin layer: most field crops draw from 0–100 cm,
so root-zone soil moisture is the physical quantity whose deficit *is*
agricultural drought. L4 also fills SMAP's ~2–3 day revisit gaps via land-surface-
model assimilation, giving a continuous daily series (no gappy revisit cadence to
fight in a downstream climatology). The cost is that L4 is a model-assimilation
product (not a pure radiometer retrieval), but for a drought *anomaly* that trade
is worth it. We keep 'sm_surface' alongside in the cache so a reviewer can compare
the two layers.

AUTH — NASA Earthdata bearer token (NO password)
=================================================
SMAP is distributed ONLY through NASA Earthdata (NSIDC DAAC / Earthdata Cloud):
there is no no-auth mirror (Planetary Computer carries 0 SMAP collections). So a
valid Earthdata bearer token is REQUIRED. CMR collection/granule *search* is
public (no token needed); only the granule data download is auth-gated. The
bearer token and download/auth helpers live in ingest/access/earthdata.py.

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/smap_loader.py. Only the raw,
geometry-parameterized `smap_timeseries` pull is kept; the drought-coded z-score
anomaly lives in tierva/kernel/climatology.py, and the demo harness was dropped.
NOT yet validated against live data in this repo.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from ..access.earthdata import (
    EarthdataAuthError,
    cmr_search,
    download,
    read_token,
)

CACHE_DIR = Path(__file__).parents[2] / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# L4 root-zone (chosen) — see module docstring. SPL3SMP_E is the L3 surface
# fallback if a reviewer wants the pure-radiometer surface layer instead.
SHORT_NAME = "SPL4SMGP"
VERSION = "008"        # latest operational SPL4SMGP collection on CMR
GROUP = "Geophysical_Data"           # HDF5 group holding sm_* variables in SPL4SMGP
RZ_VAR = "sm_rootzone"               # 0–100 cm root-zone (crop-relevant)
SURF_VAR = "sm_surface"              # top ~5 cm (kept for comparison)


def _cache_path(geom, start: str, end: str) -> Path:
    """Stable cache filename from the request (bounds + dates + product hash)."""
    key = f"{SHORT_NAME}|{VERSION}|{geom.bounds}|{start}|{end}"
    h = hashlib.md5(key.encode()).hexdigest()[:10]
    return CACHE_DIR / f"smap_{h}.parquet"


def _find_granules(geom, start: str, end: str, one_per_day: bool = True) -> list[dict]:
    """Public CMR granule search (no auth) over the bbox + date range.
    Returns list of {date, url} for the .h5 data link of each granule.

    SPL4SMGP is 3-hourly → 8 global granules/day. one_per_day=True keeps only the
    FIRST granule of each solar day, so a 5-year pull is ~1825 files instead of
    ~14,600. One daily 9-km snapshot is plenty for a monthly drought z-score, and
    avoids downloading 8x the data. (A still-leaner path is server-side
    subsetting via NSIDC Harmony / OPeNDAP.)"""
    minx, miny, maxx, maxy = geom.bounds
    out: list[dict] = []
    seen_days: set = set()
    page = 1
    while True:
        entries = cmr_search({
            "short_name": SHORT_NAME,
            "version": VERSION,
            "bounding_box": f"{minx},{miny},{maxx},{maxy}",
            "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
            "page_size": 2000,
            "page_num": page,
            "sort_key": "start_date",
        })
        if not entries:
            break
        for e in entries:
            url = None
            for link in e.get("links", []):
                href = link.get("href", "")
                if href.endswith(".h5") and href.startswith("http"):
                    url = href
                    break
            if url:
                day = pd.to_datetime(e.get("time_start")).date()
                if one_per_day and day in seen_days:
                    continue  # keep only the first 3-hourly granule of each solar day
                seen_days.add(day)
                out.append({"date": day, "url": url})
        if len(entries) < 2000:
            break
        page += 1
    return out


def _bbox_mean_from_h5(h5_path: Path, geom) -> dict:
    """Spatial mean of root-zone (and surface) soil moisture over the polygon bbox.

    Verified against the SPL4SMGP product layout (NSIDC user guide / NASA
    Openscapes tutorials): the geophysical variables live under the HDF5 group
    'Geophysical_Data', with datasets 'sm_rootzone' and 'sm_surface', and the
    EASE-Grid 2.0 M09 cell-center coordinates are 2-D arrays 'cell_lat' /
    'cell_lon' (shape 1624x3856, matching the soil-moisture grid). Fill value is
    -9999.0 (fmissing_value).

    We mask to the bbox using those coordinate arrays and nan-mean the soil-
    moisture cells inside. Defensive for either 2-D coordinate grids (the
    SPL4SMGP norm) or 1-D lat/lon axes (some sibling SMAP layouts) so the same
    reader survives a minor layout change.
    """
    import h5py

    minx, miny, maxx, maxy = geom.bounds

    def _grab(f, name):
        # tolerate either Geophysical_Data/<var> or a flat layout
        for path in (f"{GROUP}/{name}", name):
            if path in f:
                return f[path][:]
        raise KeyError(f"{name} not found in {h5_path.name}")

    with h5py.File(h5_path, "r") as f:
        rz = _grab(f, RZ_VAR).astype("float64")
        try:
            surf = _grab(f, SURF_VAR).astype("float64")
        except KeyError:
            surf = None
        lat = _grab(f, "cell_lat").astype("float64")
        lon = _grab(f, "cell_lon").astype("float64")

    fill = -9999.0
    # Build 2-D coordinate grids matching the soil-moisture array. If cell_lat /
    # cell_lon are already 2-D (SPL4SMGP), use them as-is; if a 1-D axis pair is
    # ever returned, meshgrid them to the data shape.
    if lat.ndim == 1 and lon.ndim == 1 and rz.ndim == 2 and rz.shape == (lat.size, lon.size):
        lon2d, lat2d = np.meshgrid(lon, lat)
    else:
        lat2d, lon2d = lat, lon

    rz = np.where((rz <= fill) | (~np.isfinite(rz)), np.nan, rz)
    inbox = (lat2d >= miny) & (lat2d <= maxy) & (lon2d >= minx) & (lon2d <= maxx)
    if not inbox.any():
        # tiny AOI (a 9-km cell can be wider than the bbox): fall back to the
        # single nearest grid cell to the bbox centroid.
        cy, cx = (miny + maxy) / 2.0, (minx + maxx) / 2.0
        d = (lat2d - cy) ** 2 + (lon2d - cx) ** 2
        j = np.unravel_index(np.nanargmin(d), d.shape)
        inbox = np.zeros(rz.shape, dtype=bool)
        inbox[j] = True

    res = {"sm_rootzone": float(np.nanmean(rz[inbox])) if np.isfinite(rz[inbox]).any() else np.nan}
    if surf is not None:
        surf = np.where((surf <= fill) | (~np.isfinite(surf)), np.nan, surf)
        res["sm_surface"] = (
            float(np.nanmean(surf[inbox])) if np.isfinite(surf[inbox]).any() else np.nan
        )
    else:
        res["sm_surface"] = np.nan
    return res


def smap_timeseries(geom, start: str, end: str) -> pd.DataFrame:
    """Return DataFrame[date, sm_rootzone, sm_surface] of daily area-mean SMAP L4
    soil moisture (m^3/m^3) over the AOI bbox. Cached to data_cache/ keyed on
    (product, version, bounds, dates).

    Each SPL4SMGP granule is a ~30-40 MB global 9-km HDF5, and we keep ONE
    granule/day (not all eight 3-hourly steps), so a 5-year pull is ~1825 files.
    We download each, read just the bbox cells, then DELETE the .h5 (only the tiny
    per-day bbox means are kept), so disk stays small even though each global file
    is not. The leanest path is server-side subsetting (NSIDC Harmony / OPeNDAP).

    Raises EarthdataAuthError if the Earthdata bearer token is missing/expired/rejected.
    """
    cache = _cache_path(geom, start, end)
    cols = ["date", "sm_rootzone", "sm_surface"]
    if cache.exists():
        return pd.read_parquet(cache)

    token = read_token()  # may raise EarthdataAuthError (missing token)
    grans = _find_granules(geom, start, end)
    if not grans:
        return pd.DataFrame(columns=cols)

    tmpdir = CACHE_DIR / "smap_h5_tmp"
    tmpdir.mkdir(exist_ok=True)

    rows: list[dict] = []
    for g in grans:
        h5 = tmpdir / Path(g["url"]).name
        if not h5.exists():
            download(g["url"], token, h5)  # raises EarthdataAuthError on 401/403
        try:
            vals = _bbox_mean_from_h5(h5, geom)
        except (KeyError, OSError):
            vals = {"sm_rootzone": np.nan, "sm_surface": np.nan}
        finally:
            # keep disk small: drop the global granule once its bbox mean is read
            h5.unlink(missing_ok=True)
        rows.append({"date": g["date"], **vals})

    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        # SPL4SMGP ships multiple 3-hourly granules/day in some access modes; if
        # several rows share a solar day, average them to one daily observation.
        df["date"] = pd.to_datetime(df["date"])
        df = df.groupby("date", as_index=False)[["sm_rootzone", "sm_surface"]].mean()
        df = df.sort_values("date").reset_index(drop=True)
        df.to_parquet(cache)
    return df
