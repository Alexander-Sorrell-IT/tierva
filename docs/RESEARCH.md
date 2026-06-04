# Tierva — Building Blocks (web-verified research)

*Compiled 2026-06-04 from a 6-track web sweep. Every dataset/tool/price below was web-checked. This is the
"build on this" reference for the [VISION](VISION.md). Headline: **almost the entire platform can run on FREE,
commercial-OK data** — cost is compute/hosting, not licensing — and the L3 "gardener" is mostly *wrapping* free
data (FAO GAEZ), not building climate models.*

---

## §1 — The data spine (free + paid)

**Decision-critical distinction: "free for research" ≠ "free to charge a product on."**

### (A) FREE *even for commercial use* — the real spine (all global)
- **Copernicus / Sentinel** — Sentinel-2 (10 m optical, 5-day), Sentinel-1 (C-band SAR, all-weather/cloud-piercing), Sentinel-3, Sentinel-5P. Explicitly "no restrictions on commercial or non-commercial use."
- **NASA (Earthdata; user holds a bearer token)** — MODIS + successor **VIIRS** (daily), **Landsat** (30 m, **40-yr archive** → the "history" L2 needs), **SMAP** (soil moisture), **GRACE/GRACE-FO** (groundwater), **GPM IMERG** (rainfall).
- **NASA NEX-GDDP-CMIP6** — downscaled **daily climate projections 1950–2100**, 0.25°, 8 vars × 5 SSPs × 35 models, **CC0**, on AWS S3. The data engine behind the "20-year simulation" trend layer.
- **Hosting:** AWS Registry of Open Data + Microsoft Planetary Computer serve the above as cloud-optimized/STAC. **Cheapest pull = Copernicus Data Space Ecosystem** (free, no requester-pays egress). AWS open buckets are *requester-pays* — co-locate compute in-region to zero egress. Planetary Computer throttles → use for dev/pre-cache.

### (B) FREE but NON-commercial or capped — **cannot** be the paid backbone
- **Google Earth Engine** — free tier is *noncommercial only*. Commercial = **$2,000/mo** platform fee + compute (~$1.33/online-EECU-hr). Use only for one-off batch composites if at all.
- **Sentinel Hub** (Planet-owned) — free = 30-day trial; commercial OGC ~€83/mo (managed tiling, not new data).
- **Regional (not "global"):** OpenET (ET, 30 m, **US-only**), Digital Earth Africa (**Africa-only**). Planet NICFI free tropical basemaps **ended Jan 2025**.

### (C) PREMIUM (the upsell — where the free spine *fails*)
- **Satellogic** — sub-meter, **~$4.50/km² archive / ~$12/km² tasking** (cheapest sub-meter, self-serve API).
- **Planet** — PlanetScope 3 m daily, "Area Under Management" (~€665 / 500 ha / yr); SkySat sub-meter (archive min $5k).
- **Maxar** — 30 cm, ~$15–60/km² via resellers. **SAR:** Umbra (open pricing $675–$4,750/scene), ICEYE/Capella (quote).

**→ Tierva mapping:** **L1 runs entirely on the free-commercial spine ($0 data cost)** — the existing 15 loaders +
map already cover it; the win is *packaging*, not new data. **Paid sensors are the upsell** (see §1 moat).

**Moat / where paid earns its keep:** ① **Parcel resolution** — 10 m Sentinel-2 / 30 m Landsat *cannot resolve a
smallholder's 1-acre plot* (~63 m across = a smeared pixel). The "look at MY land" promise *breaks* at free-tier
resolution → charge for the **parcel close-up** (Satellogic cheapest). ② **All-weather** — optical goes blind
under cloud exactly when floods/storms hit; **SAR (Sentinel-1 free; ICEYE/Umbra paid) sees through cloud** → the
flood/trigger-confirmation upsell.

**Top resources:** Copernicus Data Space `dataspace.copernicus.eu` · NASA Earthdata `earthdata.nasa.gov` ·
NEX-GDDP-CMIP6 `registry.opendata.aws/nex-gddp-cmip6` · Planetary Computer `planetarycomputer.microsoft.com` ·
Satellogic `satellogic.com` · Umbra pricing `umbra.space/pricing`.

---

## §2 — The "gardener" engine: 20-yr crop suitability (L3)

**The single highest-value find: FAO GAEZ already computes "what to grow now vs in 20 years," globally, for free.**
The climate science is **not** Tierva's moat — FAO did it. Tierva's moat is the *consumer fusion* (below).

- **FAO GAEZ v5** (Apr 2025) — **crop-suitability index (0–10000) at ~1 km for 70+ crops**, baseline (2001–2020) **and future 2021-2040 / 2041-2060 / 2061-2080 / 2081-2100** under SSP1-2.6 / SSP3-7.0 / SSP5-8.5; rain-fed vs irrigated; soil from HWSD v2.2. Int16 GeoTIFF + WMTS. **CC-BY 4.0, free.** *This literally outputs "suitability of crop X at your pixel, now vs in 20 yrs."*
- **FAO GAEZ v4** — coarser (~9 km) but has a **live ArcGIS REST point-query API** (identify/getSamples) — instant per-lat/lon answers, zero storage.
- **ISIMIP3b** — precomputed gridded **crop-yield** projections (~50 km), cross-check.

**Concrete L3 algorithm:** from user lat/lon → sample GAEZ v5 index for every crop, baseline vs a future window
(2041–2060 = "20 yrs out"), default **SSP3-7.0** (realistic-middle; show ONE number by default, optimistic/worst
as toggles) → rank, compute Δ → message: rising-suitability crops = "**start growing X**"; the user's current
crop falling below threshold = "**Y is becoming unsuitable — switch by year N**."

**Honesty bound on "your land":** only **GAEZ v5 (~1 km)** and **WorldClim (~1 km)** are fine enough to render a
single farm. NEX-GDDP (~25 km) / ISIMIP (~50 km) are "your *region*," not your field — use them as context
overlays, never as a per-farm verdict.

**Top resources:** GAEZ v5 `data.apps.fao.org` (+ `fao.org/gaez`) · GAEZ v4 ImageServer
`gaez-services.fao.org/server/rest/services` · WorldClim CMIP6 `worldclim.org/data/cmip6/cmip6_clim30s.html` ·
C3S CMIP6 `cds.climate.copernicus.eu/datasets/projections-cmip6`.

---

## §3 — AI/ML (L2 + L3) — license/wrap, don't rebuild

**Verdict: do NOT train a foundation model or build a climate model. Wrap the free assets; build only the 3
Tierva-specific things (the fusion, the plain-language layer, the per-parcel downscaling).**

- **20-yr "what to grow"** = **FAO GAEZ v5** (above) — already built, free.
- **Yield/forecast** is mature: multi-sensor fusion (MODIS+Landsat+Sentinel-1+2+weather) → RF/GBM **R²>0.70**, peak ~0.93; TCN on Sentinel-2 beats RF.
- **Geospatial foundation models (free, commercial-OK):** **IBM-NASA Prithvi-EO-2.0** (Apache-2.0, on Hugging Face; fine-tune for crop classification/yield) · **Google AlphaEarth Satellite Embeddings** (10 m, in Earth Engine — instant land-cover/crop maps) · **GraphCast/GenCast** weather (open code+weights, beat ECMWF ensemble).
- **L1 freebies to add as new "sensors":** FAO **WaPOR v3** (ET/biomass/water-productivity) · Copernicus **EDO/GDO** drought indices (SPI/soil-moisture/NDVI anomaly — the auditable public drought signal for Pacto's trigger).
- **The advisor UX reference:** **Digital Green Farmer.Chat** — GPT-4 multilingual RAG ag advisor, 250k+ smallholders. Exact architecture template for L2/L3's conversational layer.

**Moat:** nobody ships **parcel-level (10 m) future-suitability** for free (GAEZ ~9 km, NEX-GDDP ~25 km). The win =
**fuse** GAEZ's climate envelope + NEX-GDDP trajectory + AlphaEarth 10 m embeddings + your land's real satellite
history into one downscaled, personalized, plain-language answer. Each ingredient is free; **no product assembles
them for a non-expert.**

---

## §4 — Competitive landscape & the moats

9 players mapped. **Two slots are wide open:**

- **Climate FieldView** (Bayer) — commercial row-crop growers; free Basic + Plus ~$649/yr + $649 hardware dongle. Useless to a phone-only smallholder.
- **Cropin** — B2B/B2G SaaS (Aksara GenAI agronomist); sells *around* farmers (agribusiness/govt buy; farmer is a data point). No public price.
- **Farmonaut** — closest analog: smallholder satellite app via mobile/WhatsApp, ~$10–200/mo; but subscription + index-centric. *Study its UX, beat it on the free-tier "see your land" + the 20-yr gardener.*
- **Copernicus Browser / Digital Earth Africa / Google Earth Engine** — free + powerful but **demand EO/Python literacy**.
- **OneSoil** — free, friendly NDVI app, but assumes you already manage a field and know NDVI.

**The five gaps = five places Tierva wins:**
1. **The un-degreed / zero-knowledge user** — *no one* serves "point at my home, tell me plainly what the sky sees." (L1)
2. **The global poor / smallholder** — reached only indirectly (govts/insurers buy); Farmonaut is the lone consumer attempt, still subscription/index-centric.
3. **20-yr, per-individual crop suitability** — *nobody* offers forward-looking climate-change crop advice to an individual. (L3 — clearest moat.)
4. **The giving/relief layer is entirely absent** from all 9 farm apps — it's a *separate* industry (Pula/ACRE/OKO parametric insurance). Tierva uniquely fuses consumer-EO + giving + auto-relief.
5. **Transparency** — parametric payouts are a black box to donors; Tierva's L1 map *shows the donor the exact data that fired the payout.*

---

## §5 — Map/serving tech & cost (keep it cheap)

**Letting anyone look up their land is THREE problems, each with a different cheapest answer — conflating them is
the main cost trap (esp. treating a per-location readout as tile rendering).**

1. **Basemap** (pan/zoom): **PMTiles + Protomaps** (single-file world basemap on object storage, no tile server) read by **MapLibre GL JS** via HTTP Range. Serving 10 M tile req/mo ≈ **$11 on Cloudflare R2** (zero egress) vs ~$120 AWS S3 vs ~$3,600 Google Maps.
2. **Raster overlays** (moisture/NDVI painted over an area): dynamic tiling from **COGs with TiTiler** on AWS Lambda (~$50/M tiles vs Mapbox ~$250). Sentinel-2 L2A already free COGs on AWS.
3. **Per-location readout** (the actual L1 promise — *the numbers for MY parcel*): **COG point-sampling** (`rio-tiler /point` over a STAC index) — a single Range request, **no tile rendering**. The cheapest op; the underexploited move most products miss.

**Frontend:** **keep Leaflet for the MVP** (the existing map handles raster overlays fine; one user looks at one
spot). Migrate to **MapLibre** later for vector basemaps + deck.gl (the giving/donor map). **Avoid CesiumJS**
unless a literal 3D globe is required (free tier is non-commercial → $149+/mo once Tierva is commercial). Net: a
**20–300× serving-cost reduction** by serving from object storage instead of managed tiles — the difference
between L1 being "cheap as promised" vs quietly unaffordable per user.

**Top resources:** TiTiler `github.com/developmentseed/titiler` · PMTiles/Protomaps `github.com/protomaps/PMTiles` ·
Sentinel-2 COGs `registry.opendata.aws/sentinel-2-l2a-cogs`.

---

## §6 — The giving / direct-to-farmer layer (Pacto)

**Frame it as a GIFT, not insurance.** Insurance needs a license + underwriter + reinsurer (Pula runs a Bermuda
vehicle). The clean lane = **anticipatory cash transfer / forecast-based financing** (WFP/IFRC precedent): donors
fund a pool earmarked to a farmer/region; when the satellite consensus confirms drought, the contract
auto-releases the gift. No premium, no policy. *(Counsel before any real-money pilot — see `strategy/` §12.)*

- **Tierva already has the two hardest pieces** the sector spends years building: the **satellite trigger** (15 loaders) and a **deployed smart contract**.
- **Last-mile models:** GiveDirectly (**~85% reaches recipient**, mobile-money) · Kiva (0%-fee loans via local Field Partners) · parametric precedents Pula / OKO (feature-phone USSD) / ACRE.
- **Cheapest rails = crypto:** Celo ~$0.01/tx, Stellar fractions of a cent → push pass-through toward ~95%. **Stellar Disbursement Platform** is open-source (MoneyGram cash-out ~150 countries). **Etherisc** = open parametric smart-contract scaffolding (22k+ Kenyan farmers) to study.
- **Real cost is targeting + cash-out** (mobile-money/agent fees, KYC), *not* the transfer.

**Moat:** **no consumer "fund a specific farmer and watch the satellite that protects them" product exists.**
Parametric insurers have the trigger but no donor layer; GiveDirectly/Kiva have donors but no satellite trigger.
Tierva fuses **donor-facing giving + live satellite map + self-executing payout + radical transparency.**

**Top resources:** GiveDirectly `givedirectly.org/financials` · Stellar SDP `stellar.org/products-and-tools/disbursement-platform` ·
Mercy Corps smart-contract index insurance (Kenya) · WFP Anticipatory Actions `wfp.org/anticipatory-actions` · Etherisc `etherisc.com`.

---

## Bottom line for the build

1. **L1 is ~$0 data cost and mostly built** — package the free-commercial spine, go global, serve from object storage (R2 + TiTiler), point-sample per parcel.
2. **L3 "gardener" = wrap FAO GAEZ v5** (free, already does 20-yr crop suitability) + downscale/fuse to 10 m + plain-language it. Don't build climate models.
3. **L2 = wrap open foundation models** (Prithvi / AlphaEarth / GraphCast) + a Farmer.Chat-style advisor. Don't train from scratch.
4. **Premium tier = paid sensors** (Satellogic parcel close-ups; SAR all-weather) — the honest upsell where free fails.
5. **Pacto giving = gift/forecast-based financing** on cheap crypto rails (Celo/Stellar), framed as not-insurance; you already hold the trigger + contract.
6. **The moat is the *fusion + the consumer layer*, not any single dataset** — every ingredient is free/open; nobody assembles them for a non-expert at parcel scale with a giving layer attached.
