"""Microsoft Planetary Computer STAC access — the NO-AUTH sign+search pattern.

Promoted out of the source loaders (sentinel2, sentinel1_sar, worldcover_cropland,
modis_lst, modis_ndvi) so the one shared pattern lives in one place:

    catalog = pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)
    items   = catalog.search(...).items()

Planetary Computer mirrors Copernicus (Sentinel-1/2) and NASA (MODIS, ESA
WorldCover) collections and requires **no authentication** for the open
collections used here: `pc.sign_inplace` signs the asset hrefs at search time, so
a loader that subsequently calls `odc.stac.load(items, ...)` or reads an asset
href directly (e.g. Sentinel-1 GRD `item.assets["vv"].href`) needs no further
Planetary-Computer import or token.

NOTE on the name clash: this module is `…access.planetary_computer`, but
`import planetary_computer as pc` below still resolves to the installed
third-party package (Python 3 uses absolute imports), not to this file.

TRANSCRIBED FROM the working pacto-seco loaders; NOT yet validated against live
data in this repo (no network/credentials exercised here).
"""
from __future__ import annotations

import planetary_computer as pc  # third-party lib, NOT this module (absolute import)
import pystac_client

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def open_catalog(stac_url: str = STAC_URL):
    """Open the Planetary Computer STAC catalog with in-place asset signing.

    No auth required for the open collections. Returns a pystac_client.Client.
    """
    return pystac_client.Client.open(stac_url, modifier=pc.sign_inplace)


def search(
    collections,
    geom=None,        # shapely geometry in EPSG:4326 -> intersects=geom.__geo_interface__
    bbox=None,        # [minx, miny, maxx, maxy] -> bbox= (used by worldcover_cropland)
    datetime=None,    # "start/end"
    query=None,       # STAC query dict, e.g. {"eo:cloud_cover": {"lt": 60}}
    stac_url: str = STAC_URL,
) -> list:
    """No-auth STAC search on Planetary Computer; returns a list of signed items.

    Covers both call shapes used by the loaders:
      * intersects + datetime + query  (sentinel2 / sentinel1_sar / modis_*),
      * bbox only, no datetime/query    (worldcover_cropland).

    Pass `geom` (a shapely geometry) OR `bbox` ([minx, miny, maxx, maxy]); `geom`
    is sent as `intersects=geom.__geo_interface__`. Items come back already signed
    (pc.sign_inplace), ready for odc.stac.load or direct asset-href reads.
    """
    catalog = open_catalog(stac_url)
    kwargs: dict = {"collections": list(collections)}
    if geom is not None:
        kwargs["intersects"] = geom.__geo_interface__
    if bbox is not None:
        kwargs["bbox"] = list(bbox)
    if datetime is not None:
        kwargs["datetime"] = datetime
    if query is not None:
        kwargs["query"] = query
    return list(catalog.search(**kwargs).items())
