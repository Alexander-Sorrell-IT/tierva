# `ingest/` — Tierva's Earth-observation data spine

These modules pull raw, geometry-parameterized satellite/reanalysis time series
for any AOI polygon (shapely geometry, EPSG:4326). They are the L1 "SEE" data
spine: each `*_timeseries` / `*_monthly` / `*_mask` function returns a tidy
DataFrame (or mask) of *raw values* — **no drought coding here**. The z-score /
anomaly / threshold logic (the per-month climatology, sign conventions, breach
detection) lives in `tierva/kernel/climatology.py` and the consensus kernel, not
in these loaders.

> **TRANSCRIBED, NOT VALIDATED.** Every module here is transcribed from the
> working `pacto-seco` loaders (`pacto-seco/src/pacto_seco/data/`), which *have*
> been run against live data in that project. In **this** repo they have **only
> been syntax-checked** (`ast.parse`) and import-wiring-checked; **they have NOT
> been run against live data here** — the live pulls need network access plus
> credentials (Earthdata token / CDS key) that are not exercised in this
> transcription. Treat all behavior as inherited, not re-verified.

## Layout

```
ingest/
  access/                     # 3 shared access patterns, promoted out of the loaders
    planetary_computer.py     #   no-auth Microsoft PC STAC sign+search
    earthdata.py              #   NASA CMR search + bearer-token download
    cds.py                    #   Copernicus CDS ~/.cdsapirc bootstrap
  sources/                    # per-source raw-pull loaders (import from access/)
    sentinel2.py  sentinel1_sar.py  worldcover_cropland.py   # PARCEL-CAPABLE (10 m)
    modis_ndvi.py                                            # field-to-region (250 m)
    smap.py  era5_rain.py  chirps.py  modis_lst.py           # region-only context
```

## Resolution tiers — what each source can actually resolve

Honest about spatial resolution: only the 10 m tier resolves a single parcel.
Everything coarser is a regional/contextual read averaged over the AOI bbox.

| Tier | Can resolve | Sources (modules) |
|---|---|---|
| **Parcel-capable (10–20 m)** | a single field / parcel | **Sentinel-2** NDVI `sentinel2.py` · **Sentinel-1 SAR** `sentinel1_sar.py` · **ESA WorldCover** cropland `worldcover_cropland.py` |
| **Field-to-region (250 m)** | a field block, not one parcel | **MODIS-NDVI** `modis_ndvi.py` |
| **Region-only context (1 km → ~9 km)** | a regional average over the AOI | **MODIS-LST** `modis_lst.py` (1 km) · **CHIRPS** rainfall `chirps.py` (~5 km) · **SMAP** soil moisture `smap.py` (~9 km) · **ERA5-Land** rainfall `era5_rain.py` (~9 km) |

> Tierva's per-parcel L1 view rides on the three **10 m** sources
> (Sentinel-2 / SAR / WorldCover). The rest are honestly labelled regional context.

## Auth needs

| Access module | Auth | How |
|---|---|---|
| `access/planetary_computer.py` | **NONE** | Microsoft Planetary Computer signs asset hrefs in-place at search time (`pc.sign_inplace`). No key, no login. Used by Sentinel-2, Sentinel-1 SAR, WorldCover, MODIS-NDVI, MODIS-LST. |
| `access/earthdata.py` | **Earthdata bearer token** | JWT from `EARTHDATA_TOKEN` env var, else `~/.edl_token`. CMR *search* is public; only the granule *download* is token-gated (401/403 → `EarthdataAuthError`). Used by SMAP. |
| `access/cds.py` | **Copernicus CDS key** | Personal access token written to `~/.cdsapirc` by `setup_cdsapirc(key)`; the `cdsapi` client reads that file. Used by ERA5-Land rainfall. |

## Not yet ported (deferred — need the `generalize` fixes from the build plan)

These exist in `pacto-seco` but were intentionally skipped here because they carry
Honduras-specific hardcoding that must be generalized before they belong in a
global ingest layer (see `tierva/docs/BUILD_PLAN.md`):

- **`ccism`** — `BBOX_PAD = 0.4°` silently averages ~40 km of neighbours; the pad
  must be exposed per-call and the source labelled region-only.
- **`goes` (GOES-LST)** — `DEFAULT_HOUR_UTC = 19` (Honduras local noon) and
  `noaa-goes16` (Americas-only); needs globalizing (derive the local-solar hour
  from longitude, pick the satellite by region: GOES-E/W, Himawari, Meteosat).
- **`fapar`** — superseded by the project's own `cgls_fapar`; lift only if a
  coarse global FPAR fallback is wanted.

## What was dropped in transcription

For each ported loader, three surgical edits vs the pacto-seco original:
1. dropped the `__main__` Honduras demo (Concepción de María, Choluteca);
2. dropped the drought-coded `*_anomaly` z-score function(s) — that logic now
   lives in `tierva/kernel/climatology.py`;
3. renamed Honduras / Dry-Corridor / `municipio` identifiers to generic
   `AOI` / `region`, and promoted the three shared access patterns into
   `access/` so the source loaders import from them.

The load-bearing technical prose was kept verbatim (Sentinel-1's GCP/WarpedVRT
georeferencing fix, SMAP's SPL4SMGP product choice, the MODIS mask-fill-before-
scale ordering), because those are correctness notes, not domain coding.
