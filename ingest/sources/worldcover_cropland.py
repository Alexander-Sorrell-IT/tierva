"""Cropland mask from ESA WorldCover, via Microsoft Planetary Computer (no auth).
PARCEL-CAPABLE (10 m).

Why: a per-AOI NDVI spatial-mean mixes forest, town, water and bare ground in
with the actual farmland. For a food-security / drought signal we want NDVI of
CROPLAND only. ESA WorldCover is a global 10 m land-cover map; pixels with class
value 40 are Cropland. We build a boolean mask (True = cropland) on the same bbox
grid and apply it to the NDVI cube before taking the area-mean.

Auth: NONE (Planetary Computer signs assets in-place at search time).

Source facts (verified against real sources, not invented):
  - Collection id : "esa-worldcover"
      https://planetarycomputer.microsoft.com/dataset/esa-worldcover
  - Map band/asset: "map"  (loaded via odc.stac, accessed as ds["map"])
      https://github.com/microsoft/PlanetaryComputerExamples/blob/main/datasets/esa-worldcover/esa-worldcover-example.ipynb
  - Class value   : 40 = Cropland  (LCCS scheme: 10 tree, 20 shrub, 30 grass,
      40 CROPLAND, 50 built-up, 60 bare, 70 snow/ice, 80 water, 90 wetland,
      95 mangrove, 100 moss/lichen)
      https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf

How a caller applies the mask to an NDVI cube
---------------------------------------------
The mask comes back as a 2-D boolean DataArray on its own grid. NDVI (see
sentinel2.ndvi_timeseries) is usually loaded at a *finer* resolution, so the two
grids do not share coordinate labels. `.where()` aligns by coordinate
intersection, so you must regrid the mask onto the NDVI grid first (nearest
neighbour — never interpolate a categorical class map), then mask, then average.

`rio.reproject_match` cannot warp a boolean raster — rasterio has no GDAL dtype
for ``bool`` and raises ``KeyError('bool')`` — so carry the mask through the
regrid as ``uint8`` (1 = cropland, 0 = not), declare 0 as nodata, resample with
nearest neighbour, then re-threshold with ``> 0``::

    from rasterio.enums import Resampling
    from ingest.sources.worldcover_cropland import cropland_mask

    mask = cropland_mask(geom)                       # 2-D bool, True = cropland
    mask = (mask.astype("uint8")                     # bool -> uint8 (rasterio-safe)
                .rio.write_crs("EPSG:4326")
                .rio.write_nodata(0)
                .rio.reproject_match(ndvi, resampling=Resampling.nearest))
    ndvi_crop = ndvi.where(mask > 0)                 # non-cropland pixels -> NaN
    cropland_mean = ndvi_crop.mean(dim=("y", "x"))   # area-mean over cropland only

If the NDVI cube already sits on this exact bbox+resolution grid you can skip the
reproject and use `ndvi.where(mask)` directly (a bool mask works fine in
`.where()`; the uint8 cast is only needed for `reproject_match`).

TRANSCRIBED FROM pacto-seco/src/pacto_seco/data/cropland.py. The raw,
geometry-parameterized `cropland_mask` is kept; the demo harness was dropped.
NOT yet validated against live data in this repo.
"""
from __future__ import annotations

import numpy as np
import rioxarray  # noqa: F401  (registers the .rio accessor used by callers)
import odc.stac
import xarray as xr

from ..access.planetary_computer import search

WORLDCOVER_COLLECTION = "esa-worldcover"
WORLDCOVER_MAP_BAND = "map"
CROPLAND_CLASS = 40  # ESA WorldCover LCCS: 40 = Cropland


def cropland_mask(geom, resolution: float = 0.0018) -> xr.DataArray:
    """Boolean cropland mask (True where cropland) on the geom's bbox grid.

    Parameters
    ----------
    geom : shapely geometry in EPSG:4326 (e.g. an AOI / parcel polygon).
    resolution : grid spacing in degrees (~0.0018 deg ~= 200 m). Default is
        deliberately coarse for speed; pass a finer value to match an NDVI grid,
        or regrid the returned mask onto the NDVI grid (see module docstring).

    Returns
    -------
    xarray.DataArray of dtype bool, dims (y, x), CRS EPSG:4326, True where the
    WorldCover class is Cropland (40). No authentication required.
    """
    minx, miny, maxx, maxy = geom.bounds
    bbox = [minx, miny, maxx, maxy]

    items = search(collections=[WORLDCOVER_COLLECTION], bbox=bbox)
    if not items:
        # No WorldCover coverage for this bbox: return an all-False mask on a
        # 1x1 grid centred on the bbox so callers don't hit a bare IndexError.
        return xr.DataArray(
            np.zeros((1, 1), dtype=bool),
            dims=("y", "x"),
            coords={"y": [(miny + maxy) / 2.0], "x": [(minx + maxx) / 2.0]},
        ).rio.write_crs("EPSG:4326")

    ds = odc.stac.load(
        items,
        bands=[WORLDCOVER_MAP_BAND],
        bbox=bbox,
        resolution=resolution,
        crs="EPSG:4326",
        chunks={},
        fail_on_error=False,  # skip unreadable COG tiles instead of crashing
    )

    # The esa-worldcover collection holds multiple map versions (2020 v100 and
    # 2021 v200), so odc.stac returns a stray `time` axis. Take the latest map
    # and collapse to a clean 2-D grid — otherwise the mask would broadcast
    # against NDVI's time axis and produce garbage.
    land_cover = ds[WORLDCOVER_MAP_BAND]
    if "time" in land_cover.dims:
        land_cover = land_cover.isel(time=-1)

    mask = land_cover == CROPLAND_CLASS
    mask = mask.astype(bool)
    mask = mask.rio.write_crs("EPSG:4326")
    return mask
