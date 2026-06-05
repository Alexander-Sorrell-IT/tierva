"""ERA5-Land rainfall loader — the rainfall ground-truth. REGION-ONLY CONTEXT (~9 km).

Pulls ERA5-Land monthly total precipitation over an AOI (area-mean over the bbox).
This is the sensor that DISAMBIGUATES a dry-season greenness dip from a real
rainfall deficit downstream.

AUTH — Copernicus CDS personal access token, written to ~/.cdsapirc by
`setup_cdsapirc` (re-exported here from ingest/access/cds.py). Call it once with
your token, then `precip_monthly` constructs `cdsapi.Client()` which reads that file.
Dataset: reanalysis-era5-land-monthly-means (free, Copernicus).

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/era5_loader.py. Only the raw,
geometry-parameterized `precip_monthly` pull is kept; the drought-coded SPI-3
z-score anomaly (`spi3_anomaly` / `attach_spi3_to_scenes`) lives in
tierva/kernel/climatology.py, and the demo harness was dropped. NOT yet validated
against live data in this repo.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

# Re-export the CDS ~/.cdsapirc bootstrap so callers can `from ingest.sources.era5_rain
# import setup_cdsapirc`; the single implementation lives in the shared access module.
from ..access.cds import setup_cdsapirc  # noqa: F401  (re-exported for callers)

CACHE_DIR = Path(__file__).parents[2] / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def precip_monthly(geom, start_year: int, end_year: int, name: str) -> pd.DataFrame:
    """Monthly mean total precipitation (area-mean over the AOI bbox).
    Returns DataFrame[date(month-start), precip]. Cached per AOI name."""
    import cdsapi
    import xarray as xr

    cache = CACHE_DIR / f"era5_{name.replace(' ', '')}_{start_year}_{end_year}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)

    minx, miny, maxx, maxy = geom.bounds
    # CDS area is [North, West, South, East]; pad a touch so a tiny AOI still has a cell
    pad = 0.1
    area = [maxy + pad, minx - pad, miny - pad, maxx + pad]
    target = CACHE_DIR / f"era5_{name.replace(' ', '')}_{start_year}_{end_year}.nc"

    c = cdsapi.Client()
    c.retrieve(
        "reanalysis-era5-land-monthly-means",
        {
            "product_type": "monthly_averaged_reanalysis",
            "variable": "total_precipitation",
            "year": [str(y) for y in range(start_year, end_year + 1)],
            "month": [f"{m:02d}" for m in range(1, 13)],
            "time": "00:00",
            "area": area,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        str(target),
    )

    # CDS may still ship a zip containing the .nc — handle both.
    import zipfile
    nc_path = target
    if zipfile.is_zipfile(target):
        outdir = CACHE_DIR / f"era5_{name.replace(' ', '')}_extract"
        outdir.mkdir(exist_ok=True)
        with zipfile.ZipFile(target) as z:
            ncs = [n for n in z.namelist() if n.endswith(".nc")]
            z.extractall(outdir)
        nc_path = outdir / ncs[0]
    ds = xr.open_dataset(nc_path)
    var = "tp" if "tp" in ds else list(ds.data_vars)[0]
    # spatial mean over the bbox; tp is m/day (monthly mean) — relative scale is fine for a z-score
    da = ds[var].mean(dim=[d for d in ds[var].dims if d not in ("time", "valid_time")])
    tcol = "valid_time" if "valid_time" in ds.coords else "time"
    df = pd.DataFrame({
        "date": pd.to_datetime(ds[tcol].values),
        "precip": np.asarray(da.values).ravel(),
    }).sort_values("date").reset_index(drop=True)
    df.to_parquet(cache)
    return df
