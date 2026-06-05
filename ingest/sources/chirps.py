"""CHIRPS rainfall loader — a FULLY NO-AUTH, drought-designed INDEPENDENT rainfall
source (independent of the ERA5-Land reanalysis lineage). REGION-ONLY CONTEXT (~5 km).

WHY CHIRPS (and why it is a genuine independent witness)
========================================================
ERA5-Land (era5_rain.py) is a *reanalysis* (a physics model nudged by assimilated
observations). CHIRPS is built from a completely different lineage: it blends
satellite cold-cloud-duration infrared rain estimates (geostationary thermal IR)
with in-situ station gauges — no shared physics, no shared input stream with ERA5.
So if CHIRPS *also* shows a rainfall deficit, the rainfall signal is corroborated
across two independent sources, not an artifact of one model. CHIRPS was
purpose-built by UCSB/USGS for drought early warning (it underpins FEWS NET).

CHIRPS 2.0, global monthly, 0.05°, 1981-present. Distributed open (NO KEY) at
https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/ as one gzipped
GeoTIFF per month (chirps-v2.0.YYYY.MM.tif.gz).

Auth: NONE. No key, no token, no ~/.cdsapirc — plain HTTPS GET from a public mirror.

CHIRPS-SPECIFIC HANDLING
========================
  * UNITS: each CHIRPS monthly tif pixel is ALREADY the MONTHLY TOTAL rainfall in
    mm (do NOT multiply by days-in-month; contrast ERA5 'tp', which is a mean
    daily rate). A downstream 3-month rolling sum is the plain sum of three totals.
  * NODATA: CHIRPS fill value is -9999.0 (ocean / no-data). We mask it before the
    area-mean or it would poison the bbox nanmean.
  * GZIP: the .tif.gz cannot be window-read (gzip forces a full decompress), so we
    download the whole ~14 MB monthly global file, decompress, read just the AOI
    bbox cells, then DELETE the global tif — only the tiny per-month bbox mean is
    kept. Disk stays small; reruns are free from the parquet cache.

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/chirps_loader.py. Only the raw,
geometry-parameterized `chirps_timeseries` pull is kept; the drought-coded SPI-3
z-score anomaly lives in tierva/kernel/climatology.py, and the demo harness was
dropped. NOT yet validated against live data in this repo.
"""
from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CACHE_DIR = Path(__file__).parents[2] / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# UCSB Climate Hazards Center — open, no-auth mirror.
BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"
NODATA = -9999.0


def _cache_path(geom, start_year: int, end_year: int) -> Path:
    """Stable cache filename from the request bounds + year range."""
    minx, miny, maxx, maxy = geom.bounds
    key = f"{minx:.4f}_{miny:.4f}_{maxx:.4f}_{maxy:.4f}_{start_year}_{end_year}"
    return CACHE_DIR / f"chirps_{key}.parquet"


def _month_bbox_mean(geom, year: int, month: int) -> float:
    """Download one global CHIRPS monthly tif, read the AOI-bbox area-mean (mm),
    then delete the global file. -9999 nodata masked before the mean."""
    import rioxarray  # noqa: F401  (registers the .rio accessor)
    import xarray as xr

    fname = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
    url = f"{BASE_URL}/{fname}"
    tmpdir = CACHE_DIR / "chirps_tif_tmp"
    tmpdir.mkdir(exist_ok=True)
    gz_path = tmpdir / fname
    tif_path = tmpdir / fname[:-3]  # strip .gz

    try:
        # download the gzipped global monthly tif (~14 MB)
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            tmp = gz_path.with_suffix(gz_path.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.rename(gz_path)
        # decompress (gzip can't be window-read; must fully inflate)
        with gzip.open(gz_path, "rb") as fin, open(tif_path, "wb") as fout:
            shutil.copyfileobj(fin, fout)

        minx, miny, maxx, maxy = geom.bounds
        da = xr.open_dataarray(tif_path, engine="rasterio").squeeze()
        # clip to the AOI bbox (CHIRPS is EPSG:4326, lon/lat degrees)
        clip = da.rio.clip_box(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
        vals = clip.values.astype("float64")
        # mask CHIRPS nodata (-9999) AND any declared rio nodata before the mean
        nodata = clip.rio.nodata
        mask = (vals == NODATA) | (~np.isfinite(vals))
        if nodata is not None:
            mask |= (vals == nodata)
        vals = np.where(mask, np.nan, vals)
        da.close()
        return float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan
    finally:
        # keep disk small: drop both the global tif and its gzip
        gz_path.unlink(missing_ok=True)
        tif_path.unlink(missing_ok=True)


def chirps_timeseries(geom, start: str, end: str) -> pd.DataFrame:
    """Monthly area-mean CHIRPS rainfall (mm) over the AOI bbox.

    Returns DataFrame[date(month-start), precip] where 'precip' is the CHIRPS
    monthly TOTAL rainfall in mm, area-averaged over the bbox. Cached to
    data_cache/ keyed on (bounds, year-range). The cache is written incrementally
    so a mid-run network blip never costs the whole pull.

    `start`/`end` accept 'YYYY' or 'YYYY-MM-DD'; the range is taken at month grain.
    """
    start_year = int(str(start)[:4])
    end_year = int(str(end)[:4])
    cache = _cache_path(geom, start_year, end_year)
    if cache.exists():
        return pd.read_parquet(cache)

    rows: list[dict] = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            val = _month_bbox_mean(geom, year, month)
            rows.append({"date": pd.Timestamp(year, month, 1), "precip": val})
            # incremental checkpoint so a network drop mid-pull is recoverable
            pd.DataFrame(rows).to_parquet(cache)
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df.to_parquet(cache)
    return df
