# Tierva — Global Rollout (the executable map: Honduras → worldwide)

*Compiled 2026-06-04. This is the **executable layer** on top of [RESEARCH.md §5](RESEARCH.md) (map/serving
tech + costs — applied here, not re-derived), [VISION.md](VISION.md) (L1/L2/L3), and [BUILD_PLAN.md](BUILD_PLAN.md)
(Phase 0/1/2). The trigger→payout spine is **already built and proven** (kernel test-green, contract on anvil,
oracle pushed real 2023 series, real drought fired, real USDC claimed). Global rollout is a **different axis** —
geographic + product reach — layered on that built spine. Nothing below restarts the spine; it widens it.*

> **The one-line thesis:** the data layer is already AOI-agnostic (proven live on a California parcel today). What
> stands between "Honduras-only" and "anywhere on Earth" is **not new data and not new science** — it is (1) a
> frontend that takes a user-drawn/geocoded geom instead of a Honduras GeoJSON, (2) a **point-sample fast path** so
> a single-parcel readout is interactive instead of minutes, and (3) a thin cache so we don't recompute. Three
> engineering jobs, all on the free-commercial spine, $0 new data cost.

---

## What is already global (do not rebuild)

Confirmed by reading the code, not assumed:

- **Every loader is geom/bbox-parameterized.** `sentinel2.ndvi_timeseries(geom, …)`, `sentinel1_sar.sar_timeseries(geom, …)`,
  `smap.smap_timeseries(geom, …)`, `chirps.chirps_timeseries(geom, …)`, `worldcover_cropland.cropland_mask(geom, …)`,
  `modis_*`, `era5_rain.precip_monthly(geom, …)` — all take an arbitrary shapely geom in EPSG:4326. **Proven live
  today**: `sentinel2.ndvi_timeseries` pulled real NDVI (mean 0.378) for a California Central Valley parcel
  (lon -119.70, lat 36.60) with no auth via Planetary Computer. The loaders are not Honduras-bound; the *webapp* is.
- **The kernel climatology is AOI-agnostic.** `kernel/climatology.py::monthly_climatology(df, value_col, baseline_years)`
  computes the per-month "normal" from *whatever* series and baseline-year list you hand it. Anomalies already work
  anywhere on Earth **today** — there is nothing Honduras-specific in the math. (See §4 — the gap there is
  cost/cache, not correctness.)
- **The consensus trigger is direction-agnostic and config-driven.** `kernel/consensus.py::apply_consensus_trigger`
  takes `threshold / min_sensors / persistence_days / direction` per call. A new region/vertical is a config, not a
  code fork.

**Conclusion:** the Honduras coupling lives in exactly two places — the **webapp** (`/api/municipios` loads
`honduras_dry_corridor`; `/api/dcsi/{municipio}` reads a precomputed `data_cache` keyed by municipio token; the map
hardcodes `setView([13.8,-86.9],7)`) and a **`name`-coupled cache key** in some loaders (`era5_rain` takes a `name`;
`sentinel2`'s caller named cache files by municipio). Everything else is already worldwide.

---

## §1 — AOI generalization (accept any parcel on Earth)

The data layer is done. The remaining work is the *entry point*: replace "click a Honduras municipio polygon" with
"drop a pin / draw a box / geocode an address → a shapely geom" anywhere.

**1.1 Frontend (Leaflet, keep it per RESEARCH §5).** The existing `index.html` already runs Leaflet. Add:
- `L.Control` draw-a-rectangle / drop-a-marker (Leaflet.draw or a single click→small-box). On click, build a geom
  (a point buffered to a default parcel box, or the drawn rectangle) → `POST /api/parcel {geojson}`.
- A geocoder (Nominatim free tier for MVP; cap rate) so "type your town" → lat/lon → same geom path. Address →
  parcel is the zero-knowledge L1 promise from RESEARCH §4 gap #1.
- Remove the `setView([13.8,-86.9],7)` Honduras lock; default to the geocode/geolocate result, world zoom otherwise.

**1.2 Backend.** Replace the two Honduras-bound endpoints:
- **Delete the dependency on** `/api/municipios` (the 136 Dry Corridor GeoJSON) and the `resolve_token` →
  `data_cache/ndvi_{token}_*.parquet` lookup. Those assume a fixed gazetteer of pre-cached areas.
- **Add `POST /api/parcel`**: accept a GeoJSON geom → call the loaders directly with that geom (point-sample path,
  §2) → run `climatology.zscore_anomaly` (§4) → return the readout. No gazetteer, no precompute requirement.
- **Drop the `name` coupling in the cache key.** The SAR/SMAP/CHIRPS loaders already show the right pattern: hash
  `geom.bounds` (+ dates + resolution) for the cache filename (`sentinel1_sar._cache_path`, `smap._cache_path`,
  `chirps._cache_path`). Make `sentinel2` and `era5_rain` use the same geom-hash key so an arbitrary AOI caches
  without a human-assigned name. This is the single code change that unbinds caching from Honduras.

**1.3 The constraint the naive version ignores — bound the compute per request.** A live global per-AOI pull is
**unbounded work per HTTP request**: a user can draw a 50,000 km² box over a multi-year range and trigger a massive
`odc.stac.load`. That is not optional to fix — it is part of "executable":
- **Area cap** on `/api/parcel` (e.g. reject > N km²; suggest the user zoom to a parcel). L1's promise is "YOUR
  land," so a small AOI is the *correct* product, not a limitation.
- **Route by AOI size**: parcel-scale → point-sample fast path (§2, no dask); region-scale (over the cap, internal
  only) → the batch `odc.stac.load` path. The crossover is explicit in §2.
- **Date-range cap** for the interactive call (last N months for the "now" readout; full history is the cached
  baseline build in §4, done once per cell, not per request).

---

## §2 — The PERFORMANCE fix (two primitives, not one)

This is the difference between L1 being usable globally and not. There are **two distinct read paths** and the
current code uses the heavy one for everything. Spec both; state the crossover.

### Today's bottleneck (measured)
`sentinel2.ndvi_timeseries` does two slow things:
1. It always uses the heavyweight **stack-load** path (`odc.stac.load` builds a lazy dask cube over the whole AOI ×
   all scenes × 3 bands), then
2. it reduces with a **sequential python loop** — `for t in ndvi.time.values: frame.values.ravel()` (lines 64–77),
   ~4 s/scene because each iteration materializes one scene to numpy on the host. A wide date range = minutes.

### Fix A — Parcel/field readout = COG point-sampling (the MVP, the interactive path)
This is RESEARCH §5's *"per-location readout — the cheapest op, the underexploited move most products miss."* For a
single parcel, **do not call `odc.stac.load` or build a dask graph at all**:
- Use **`rio-tiler` `/point` (or a windowed `rasterio` read)** over the STAC items: one HTTP **Range** request per
  band per scene reads only the few pixels covering the parcel, server-side, no tile rendering, no full-scene
  decode. Compute NDVI = (B08−B04)/(B08+B04) on those few pixels; SCL-mask the same window. **Return the same
  3-column schema as Fix B** — `ndvi_mean / ndvi_std / valid_frac` over the few-pixel window — so `/api/parcel →
  zscore_anomaly` consumes both read paths identically and they never silently diverge in output shape.
- **Concurrency is the load-bearing part — do not write a sequential loop.** A year of cloud-filtered S2 is ~40–70
  usable scenes × 3 assets (B04/B08/SCL) ≈ **~150 Range requests**, each ~100–300 ms round-trip to S3. Done
  *sequentially* that is 20–40 s — faster than full-scene decode but **still not interactive**, the same
  serialization failure mode as the `for t in ndvi.time.values` loop we are killing, just at smaller per-iteration
  cost. **Fan the reads out concurrently across the scene list** (thread pool / async over the STAC items). At
  ~16-way concurrency, ~150 reads → **~2 s**. That concurrency — not the Range request alone — is what makes
  "sub-second-to-seconds" true.
- Cost/latency: a parcel readout becomes **~150 small concurrent Range requests** instead of decoding whole scenes
  — ~2 s for a year of S2, the difference between L1 feeling interactive vs. "come back in 5 minutes."
- This is the path `POST /api/parcel` (§1) calls. It is the MVP read path.

### Fix B — Region/municipio timeseries = vectorized `odc.stac.load` + one `.compute()`
For an actual area (the Pacto trigger over a municipio, the donor/region overlay), keep `odc.stac.load`, but kill
the python loop:
- Replace `for t in ndvi.time.values …` with a **vectorized reduce over the spatial dims** and a **single**
  `.compute()` (or `.mean(dim=("y","x")).compute()` on the dask cube). One graph, one execution, dask parallelizes
  across scenes — instead of 1 host materialization per scene.
- **Preserve all three columns the downstream consumes** — `ndvi_mean = ndvi.mean(dim=spatial)`,
  `ndvi_std = ndvi.std(dim=spatial)`, `valid_frac = good.mean(dim=spatial)`. The webapp (`api_dcsi`) and the kernel
  read `ndvi_mean` (+ std/valid_frac plumbing); a naive `.mean()` that drops std/valid_frac is a **regression** —
  do not "simplify" them away.

### The crossover (state it explicitly)
- **AOI ≈ a parcel/field (under the area cap):** Fix A (point-sample, no dask). Interactive, per-request.
- **AOI = a region/municipio (batch, internal, cache-warming):** Fix B (`odc.stac.load` + vectorized `.compute()`).

`/api/parcel` routes by AOI area to pick the path (ties back to §1.3's area cap).

---

## §3 — Serving infra (apply RESEARCH §5; sequence it, don't list it flat)

RESEARCH §5 already proved the cost math (a 20–300× serving-cost reduction by serving from object storage instead
of managed tiles — $11/mo R2 vs $3,600 Google for 10 M tiles). **Apply it; don't re-derive it.** The key sequencing
note from RESEARCH §5: *"keep Leaflet for the MVP."* So:

**MVP needs NO new infra.** The single-parcel readout is the cheapest op in the whole stack:
- The **`/api/parcel` point-sample endpoint** (§2 Fix A) lives **inside the existing FastAPI** `server.py`.
- The **existing Leaflet map** + a click/draw marker (§1.1) is the whole frontend.
- Basemap: keep the current free Carto/OSM raster tiles for MVP. No tile server, no R2, no TiTiler needed to ship
  M0. The per-parcel readout is a Range request to public Sentinel-2 COGs (`registry.opendata.aws/sentinel-2-l2a-cogs`)
  — object storage we don't host.

**Scale infra (M1+, when overlays + the donor map arrive) — what to actually stand up:**
1. **Basemap → PMTiles + Protomaps on Cloudflare R2**, read by MapLibre GL via HTTP Range. Single-file world
   basemap, no tile server, **$11/mo at 10 M req** (RESEARCH §5). Stand up: one R2 bucket + one Protomaps PMTiles
   build. Needed only when we migrate Leaflet→MapLibre for vector basemaps + the deck.gl donor map.
2. **Raster overlays (moisture/NDVI painted over an area) → TiTiler on AWS Lambda** over the free Sentinel-2 L2A
   COGs (~$50/M tiles vs Mapbox ~$250). Stand up: TiTiler Lambda deploy + CloudFront. Needed when the product shows
   a *painted area* (region context, the donor map), not just a parcel number.
3. **Per-location readout → already covered by §2 Fix A** (`rio-tiler /point`). This is the L1 promise and the
   cheapest op; it ships in the MVP FastAPI with no extra infra. Do not let it get conflated with tile rendering —
   that conflation is RESEARCH §5's named cost trap.

**Frontend migration:** Leaflet (MVP) → MapLibre (M1, vector basemap + deck.gl donor map). **Avoid CesiumJS** unless
a literal 3D globe is required (its free tier is non-commercial → $149+/mo once Tierva is commercial — RESEARCH §5).

---

## §4 — Per-region climatology baselines ("normal for YOUR land," anywhere)

**Reframe (this is the load-bearing correction): anomalies already work globally today.** `climatology.py` is
AOI-agnostic — hand it a parcel's pulled history + a list of baseline years and it returns the per-month normal and
the z-score anywhere on Earth. There is **no Honduras-specific baseline** in the math; the "ad hoc baseline" today
is just *the webapp passing `BASELINE_YEARS=[2019..2022]` against precomputed Honduras parquet.* So §4 is **cost +
latency + caching**, not correctness.

Two real gaps remain:

**4.1 You must pull enough history per parcel to *form* a baseline.** A z-score needs several years of monthly
observations (≥2 per month for a std; more is better). For an arbitrary new parcel, that history isn't pulled yet —
pulling 4–5 years of S2/CHIRPS/SMAP on the first request would blow the interactive budget. So:
- **MVP (works today, no cache):** compute the baseline from the **parcel's own pulled history** in the same call.
  Cap the history window so it stays inside the budget (e.g. last 3 yrs monthly composites via the point-sample path).
  This already works — it is exactly what `zscore_anomaly` does; it just needs the history series fed in.
- The honest UI note when history is thin: a baseline from <N years is provisional; `monthly_climatology` already
  logs a warning for months with <2 baseline obs (NaN std) — surface that as "baseline still warming up" rather than
  a confident anomaly.

**4.2 A gridded climatology cache so neighbors share a normal (M1, the scale move).** Recomputing a 5-year baseline
per parcel per request is wasteful and slow. Cache it:
- **Key:** `(coarse spatial cell × month × variable)` where the cell is an **H3 / geohash / rounded-tile** id (e.g.
  H3 res 6–7, ~a few km). Neighboring parcels fall in the same cell and **share one cached normal** — one expensive
  baseline build amortized across every user in that cell.
- **Value:** `clim_mean, clim_std` per month per variable (NDVI, SPI-3/CHIRPS, SMAP, …) — the exact two numbers
  `monthly_climatology` produces.
- **Storage:** a Parquet/SQLite (MVP) or a small KV (R2/DynamoDB at scale), keyed `cell|month|variable`. A readout
  then = point-sample the *current* value (§2 Fix A, fast) + a **cache lookup** for the normal → instant z-score. No
  per-request multi-year pull.
- **Build:** a background job warms cells (on first request for a cell, or pre-warm a launch region) via the **batch
  path (§2 Fix B)** over the cell's bbox, writing the per-month normals once. This is where region-scale `odc.stac.load`
  earns its keep — warming a cache, not serving a request.

Net: MVP uses the parcel's own history (works now); M1 adds the gridded cache so it's instant and cheap at scale.

---

## §5 — The resolution-honesty matrix, applied globally

The honesty bound from the project STATE and RESEARCH §1/§2 holds **everywhere on Earth** (resolution is a sensor
property, not a place property). What changes at global scale is that we must enforce it as a **UI contract in the
readout itself**, because a user anywhere will zoom to their parcel and expect every layer to mean "my land."

| Layer | Native res | At a single parcel, it is… | Render label at parcel zoom |
|---|---|---|---|
| **Sentinel-2 NDVI** (10 m) | 10 m | **parcel-true** (a 1-acre plot ≈ a few pixels) | "your land" |
| **Sentinel-1 SAR** (10–20 m) | 10–20 m | **parcel-true** (all-weather, cloud-piercing) | "your land" |
| **ESA WorldCover** (10 m) | 10 m | **parcel-true** (land-cover/cropland mask) | "your land" |
| MODIS-VI / CGLS-FAPAR | 250–300 m | field→region (a smeared pixel over one plot) | "your area" |
| SMAP / ERA5 / ET / LST / CHIRPS / GOES / GRACE | 9 km–region | **region context only** | "your region" |
| GAEZ v5 / WorldClim (L3 gardener) | ~1 km | field→region (fine enough to render a farm; not a verdict) | "your area" |
| NEX-GDDP / ISIMIP (L3 trajectory) | 25–50 km | region only | "your region" |

**The UI contract (non-negotiable for global L1):** at parcel zoom, **only S2 / S1 / WorldCover may be presented as
"your land."** Everything coarser must be labeled **"your region"** *in the readout panel*, not merely in this doc.
This is the moat AND the honesty: RESEARCH §1's moat is that 10 m can't resolve a smallholder's plot → the paid
parcel close-up (Satellogic ~$4.50/km²; SAR all-weather) is the honest upsell where the free spine's resolution
fails. The free L1 tells the truth about which signals are your-land vs your-region; the paid tier removes the limit.

---

## ROLLOUT SEQUENCE (milestones, on the proven spine)

Numbered on the **geographic/product-reach axis** (M0/M1/M2), layered on BUILD_PLAN's already-done Phase 0 (kernel)
and Phase 1 (proof-unlock: deploy→oracle→trigger→payout, proven on anvil). This is the *global* dimension of
BUILD_PLAN Phase 2 (consumer platform). It does **not** restart the spine.

### M0 — "See YOUR land," anywhere (single-parcel L1 on the free spine) — *the MVP*
The smallest shippable global product: drop a pin / type an address anywhere on Earth → the satellites tell you
plainly what they see on your land. **No new infra, $0 new data cost.**
- [ ] `sentinel2` + `era5_rain` cache keys switched from `name` → geom-bounds hash (match SAR/SMAP/CHIRPS). *(§1.2)*
- [ ] `ndvi_timeseries` parcel fast path: `rio-tiler /point` / windowed COG read, no `odc.stac.load`, **reads fanned
      out concurrently** across scenes (not sequential; ~16-way → ~2 s for a year of S2), returning the
      `ndvi_mean/ndvi_std/valid_frac` schema. *(§2 Fix A)*
- [ ] `POST /api/parcel {geojson}` in the existing FastAPI: point-sample → `zscore_anomaly` (baseline from parcel's
      own history) → readout JSON. Area cap + date-range cap enforced. *(§1.2, §1.3, §4.1)*
- [ ] Leaflet: marker/draw + Nominatim geocode; drop `setView` Honduras lock; remove `/api/municipios` dependency. *(§1.1)*
- [ ] Readout panel applies the §5 UI contract (S2/S1/WorldCover = "your land"; coarser = "your region").
- **Exit:** a stranger anywhere drops a pin and gets a truthful, interactive per-parcel readout in seconds.

### M1 — Cheap & instant at scale (serving infra + gridded climatology cache)
Make M0 cheap-per-user and instant, and add painted overlays + the donor map.
- [ ] Vectorized batch path (`odc.stac.load` + single `.compute()`, preserving mean/std/valid_frac) for region pulls
      and cache-warming. *(§2 Fix B)*
- [ ] Gridded climatology cache keyed `(H3/geohash cell × month × variable)`; background warmer over launch region. *(§4.2)*
- [ ] PMTiles+Protomaps basemap on R2 + migrate Leaflet→MapLibre. *(§3 #1)*
- [ ] TiTiler-on-Lambda raster overlays over free S2 COGs (region NDVI/moisture paint; donor map). *(§3 #2)*
- **Exit:** readout is a point-sample + cache hit (instant, ~$11/mo basemap at 10 M req); region overlays render.

### M2 — Regions & verticals (widen the spine)
Each new region/vertical is a **kernel config + a cache-warm**, not a fork (consensus is direction-agnostic).
- [ ] First non-Honduras drought region (warm its climatology cells; instantiate a Pacto pool with its config).
- [ ] New verticals via `direction`: flood (water-level, `direction="above"`), heat anomaly, etc. — same kernel.
- [ ] L3 gardener wired in: GAEZ v5 point-query → 20-yr "what to grow" at the same parcel (RESEARCH §2), labeled
      "your area" per the §5 matrix.
- [ ] Premium upsell where free res fails: Satellogic parcel close-up / SAR all-weather (RESEARCH §1 moat).
- **Exit:** Tierva is a worldwide "see your land + 20-yr gardener + fund-a-farmer" platform, region-by-region, on
  the proven trigger→payout spine.

---

## Bottom line

1. **The data + kernel are already global** — proven live on a California parcel and an AOI-agnostic climatology.
   The Honduras coupling is the webapp gazetteer + a `name`-cache key, nothing more.
2. **The MVP (M0) ships with no new infra and $0 new data** — a point-sample `/api/parcel` endpoint in the existing
   FastAPI + a marker on the existing Leaflet map. The point-readout is the cheapest op in the stack (RESEARCH §5)
   and the one most products miss.
3. **The performance fix is two primitives:** point-sample for the parcel (interactive), vectorized `odc.stac.load`
   for regions/cache-warming (batch) — don't use the heavy path for a single parcel.
4. **Baselines already work anywhere;** the cache (gridded `cell×month×variable`) is the M1 cost/latency move, not a
   correctness fix.
5. **Honesty is a UI contract, applied globally:** only S2/S1/WorldCover are "your land" at parcel zoom; everything
   coarser is "your region" — in the readout, not just the doc. That honesty *is* the paid-upsell boundary.
