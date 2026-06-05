# Roadmap §01 — Finishing L1 ("see your land") — the money-ready plan

*Compiled 2026-06-04. This is the **costing** layer on top of [GLOBAL_ROLLOUT.md](../GLOBAL_ROLLOUT.md)
(the engineering scope — M0/M1/M2, the two read paths, the gridded cache, the UI honesty contract) and
[RESEARCH.md](../RESEARCH.md) §1 (data) + §5 (serving unit costs, web-verified). **It does not re-derive that
scope or re-look-up those prices — it applies them.** Every milestone below maps to a GLOBAL_ROLLOUT line item
and carries the same 7 fields: SCOPE · EFFORT · ONE-TIME $ · MONTHLY RUN $ · DEPENDENCIES · UNLOCKS · CAPITAL
TRANCHE. Capital tranches are the ones defined in [strategy/FUNDRAISING_STRATEGY](../../strategy/FUNDRAISING_STRATEGY.private.md)
§4 and [strategy/EQUITY_AND_DILUTION](../../strategy/EQUITY_AND_DILUTION.private.md): **(T1) non-dilutive grants
to the $600K floor (0% dilution, available NOW, pre-proof)** · **the proof-unlock gate (mainnet + real
disbursement + IDB — a different axis, Phase 1)** · **(T3) the $1–3M seed (post-proof, dilutive).***

---

## Where this starts from (ALREADY DONE — do not re-plan, do not re-cost)

L1 is **not** at zero. The MVP first slice is **live-validated**, so this document costs the *finish*, not the
start:

- **Phase 0 harvest** — `kernel/consensus.py` (direction-agnostic), generic `Pacto.sol` per-pool contract,
  `ingest/` data spine — test-green, committed.
- **Phase 1 proof spine** — `DeployPacto.s.sol` + `oracle.py`, proven end-to-end on local anvil (deploy → push
  series → trigger → claim).
- **M0 L1 FIRST SLICE** — `ingest/parcel.py` (point-sample fast path) + `app/server.py` `POST /api/parcel` +
  `app/web/index.html` Leaflet map, **live-validated against real NDVI / SAR / landcover** for California,
  France, and Spain parcels. The contest PactoSeco is also live on **Mantle Sepolia testnet** (clickable).

So GLOBAL_ROLLOUT's **M0 is ~70% done**: the point-sample endpoint, the parcel read path, and the map exist and
return truthful per-parcel readouts today. **What is NOT yet built and is costed here:** the rest of M0
(geom-hash cache keys, area/date caps, the §5 UI honesty contract in the panel, geocode), then **all of M1**
(global serving infra, region-context overlays + the Earthdata multi-tenant fix, the gridded climatology cache,
the batch perf path) and the L1 slice of **productization** (accounts, geocoding-at-scale, mobile).

> **Scope fence:** this is the **L1 consumer map only.** L2 (UNDERSTAND), L3 (the gardener), the giving/donor
> UX, paid-sensor adapters ([PAID_DATA.md](../PAID_DATA.md)), and mainnet+real-disbursement+IDB (Phase 1) are
> **other roadmap sections** — referenced as dependencies/unlocks, never costed here.

---

## Costing conventions (state once, apply everywhere)

**1. Dev-week → $.** One **dev-week = $4,000 ESTIMATE** loaded (a senior contractor/market rate; ~$200K/yr fully
burdened ÷ 50 wks). ONE-TIME $ = **labor (dev-weeks × $4K) + any one-time infra build** (e.g. the planet PMTiles
build, the SMAP/GRACE mirror). **Reality check:** Alex executes solo + AI, so actual cash burn is a small
fraction of these figures — but a *tranche funds the work at market rate*, so we cost at market rate. The
dev-week figure is the honest "what would this cost to hire out" a grant/seed underwrites.

**2. The "kind of person."** Called out per milestone: **geo-backend** (Python, rasterio/rio-tiler, STAC, dask),
**infra/DevOps** (R2/Lambda/CloudFront, IaC), **frontend** (MapLibre/deck.gl/Leaflet, mobile), **full-stack**
(accounts/billing).

**3. MONTHLY RUN $ is built bottom-up as Σ(user action → request count → RESEARCH §5 unit price)** — never
"users × a tile cost." That conflation (treating a per-location readout as tile rendering) is RESEARCH §5's
**named cost trap**; this doc avoids it by listing the per-user request assumptions (all tagged ESTIMATE, so the
arithmetic is auditable) under each figure. The unit prices applied are RESEARCH §5's web-verified ones:
- **Basemap (PMTiles on Cloudflare R2):** ~**$11 / 10M tile requests** (zero egress).
- **Raster overlays (TiTiler on Lambda over free S2 COGs):** ~**$50 / 1M tiles**.
- **Per-parcel readout (rio-tiler `/point`):** ~**150 small S3 Range GETs / lookup** (GLOBAL_ROLLOUT §2) — priced
  as **S3 GET + Lambda compute, NOT tiles.** S3 GET ≈ $0.0004/1k requests.

**4. What scales with users vs. what scales with geography — the load-bearing split.** (a) basemap + readout and
(e) accounts/geocoding scale with **users**; **(c) the climatology cache and (d) the batch warm scale with
covered CELLS/REGIONS, not users** — one warm per H3 cell is amortized across every user who ever looks there.
So the 1k/100k/1M columns are filled for user-scaling milestones and explicitly marked **"~flat in users"**
for the geography-scaling ones. Mechanically filling all three columns everywhere would be wrong.

**5. Requester-pays (RESEARCH §1).** The AWS Sentinel-2 L2A COGs are **requester-pays**. We **co-locate the
readout/batch compute in `us-west-2` (the bucket's region)** so cross-region egress is ~$0; the readout cost is
then GET + compute only. Stated once here; assumed in every readout/batch figure below. (Dev/pre-cache may use
Planetary Computer's no-auth STAC, which throttles — fine for warming, not for the hot path.)

---

## (a) Global serving infra — basemap + raster overlays + readout-at-scale

**SCOPE** *(GLOBAL_ROLLOUT §3 #1/#2 + M1; RESEARCH §5 — apply, don't re-derive).* Three serving primitives,
each with its own cheapest answer: **(i)** vector basemap = one planet **PMTiles file on Cloudflare R2**, read by
**MapLibre GL** over HTTP Range (migrate the MVP Leaflet→MapLibre); **(ii)** raster overlays (region NDVI/moisture
paint, the donor map) = **TiTiler on AWS Lambda + CloudFront** over the free S2 L2A COGs; **(iii)** the
per-parcel readout = the **`rio-tiler /point`** path that already ships in `ingest/parcel.py` — promoted from "one
dev box" to a horizontally-scaled, in-region (us-west-2) Lambda/container fronting the same point-sample.
**Note (RESEARCH §5, GLOBAL_ROLLOUT §3):** the MVP needs **no new infra** — (i) and (ii) are only required once
overlays + the donor map ship; the readout (iii) already runs in the existing FastAPI.

**EFFORT** ~**6 dev-weeks** total: ~2 wk infra/DevOps (R2 bucket + Protomaps PMTiles build pipeline; TiTiler
Lambda + CloudFront IaC), ~2 wk frontend (Leaflet→MapLibre migration, vector style, overlay layer), ~2 wk
geo-backend (containerize the point-sample for horizontal scale + in-region deploy + concurrency tuning to hold
the ~2 s/year-of-S2 target from GLOBAL_ROLLOUT §2).

**ONE-TIME $** ~**$24K** labor (6 wk × $4K) **+ ~$0–500 one-time** for the planet PMTiles build (a one-shot
Protomaps extract; can be run on a spot box or pulled from a community build). → **~$24K.**

**MONTHLY RUN $** — built bottom-up, per-user request assumptions are ESTIMATE:

| Component | Per-user assumption (ESTIMATE) | 1k users | 100k users | 1M users |
|---|---|---|---|---|
| **Basemap** (R2 @ $11/10M tiles) | ~100 tiles/session, ~4 sessions/user/mo → ~400 tile-req/user/mo | 0.4M req → **~$0.44** | 40M req → **~$44** | 400M req → **~$440** |
| **Readout** (S3 GET @ ~$0.0004/1k + Lambda) | ~10 lookups/user/mo × 150 Range GETs = 1,500 GET/user/mo | ~1.5M GET → **~$0.60 + ~$2 compute** | ~150M GET → **~$60 + ~$50** | ~1.5B GET → **~$600 + ~$300** |
| **Overlays** (TiTiler @ $50/1M tiles) | fires **only** when a region/donor map is painted; ~5% of users view, ~50 tiles each | trivial | ~250k tiles → **~$13** | ~2.5M tiles → **~$125** |
| **R2/COG storage + CloudFront** | basemap file + cache | ~$5 | ~$15 | ~$50 |
| **≈ TOTAL serving** | | **~$8/mo** | **~$235/mo** | **~$1,940/mo** |

The **readout cost is dominated by the *naive* multi-year history pull, not the point-sample** — that is the
entire ROI case for milestone (c); the figures above already assume the (c) cache exists (readout = 1 current
point-sample + 1 cache lookup). The naive-vs-cached comparison is shown under (c). **Overlays (TiTiler) is the
component that grows fastest toward 1M** and is *deferred* to when the donor map / region paint ships — until
then it is ~$0.

**DEPENDENCIES** the M0 readout (DONE); the geom-hash cache key fix (part of finishing M0); for full cheapness,
the (c) cache.

**UNLOCKS** cheap-per-user serving at the RESEARCH §5 promise (a **20–300× reduction vs. managed tiles** — $440
R2 vs. ~$176K Google Maps at 400M basemap req/mo); the painted region/donor map (a prerequisite for the
giving-UX section); the MapLibre + deck.gl base the donor map needs.

**CAPITAL TRANCHE** **T1 — non-dilutive grants (NOW, pre-proof).** This is exactly the build a **Stellar
Community Fund / Celo PG / Gitcoin** build award funds (serving infra for a public-good map). The
*at-scale-to-1M* hardening (autoscaling, multi-region) is **T3 (seed)** — but you only need it after traction, so
do not pre-build or pre-fund it. **Do NOT gate any of this behind the proof-unlock** (mainnet + disbursement +
IDB) — that gate is the Phase-1 giving axis, not L1 serving.

---

## (b) Region-context layers (SMAP / ERA5 / CHIRPS / GRACE) + the Earthdata multi-tenant fix

**SCOPE** *(GLOBAL_ROLLOUT §4 + §5 honesty matrix; RESEARCH §1A spine).* Serve the coarse "**your region**"
overlays honestly: SMAP (~9 km soil moisture), ERA5 (~9 km rain/temp), CHIRPS (~5 km rainfall), GRACE (~300 km,
**monthly** groundwater). Per the §5 UI contract these are **region context only, never "your land."** The
engineering content is **not** new data — every loader already exists and is geom-parameterized — it is **(1)**
wiring them into the readout panel as labeled region overlays, and **(2)** solving the **Earthdata multi-tenant
token problem.**

> **The Earthdata token problem, and its fix (cost the fix, not just the flag).** SMAP and GRACE come from NASA
> Earthdata, which requires a **bearer token**. The only token in hand is **Alex's personal one** (`~/.edl_token`,
> per MEMORY; **expires 2026-07-29**). A single personal bearer token **cannot back a multi-tenant product** — you
> cannot put one human's NASA credential on the hot path for thousands of users (rate limits, ToS, expiry, no
> per-user auth). **The fix:** these layers are **coarse and slow-moving** (9 km–300 km; GRACE is monthly), so
> they are **pre-cached server-side under a single org/app EDL credential (or one-time mirrored to R2), never
> fetched per-user with Earthdata auth.** The multi-tenant problem therefore **dissolves into the (c) cache** — it
> is not a separate per-user line. A user's "your region" overlay is then an R2/cache read, zero Earthdata calls
> on the hot path. (Copernicus/CDS layers like ERA5 have the same answer: bootstrap one app key, pre-cache.)

**EFFORT** ~**4 dev-weeks** geo-backend: ~1.5 wk a one-time mirror/ingest job (SMAP/GRACE/CHIRPS/ERA5 → COG/Zarr
on R2 under an org credential, on the coarse grid), ~1.5 wk wire the 4 layers into the readout panel +
TiTiler overlay rendering, ~1 wk the §5 honesty labels ("your region") + the "baseline still warming up" note.

**ONE-TIME $** ~**$16K** labor + **~$200–1,000 one-time** mirror compute/transfer (a bounded historical pull of
coarse grids; small because the grids are coarse) → **~$17K.**

**MONTHLY RUN $** — **scales with geography (cells covered), ~flat in users.** Once a region's coarse grid is
mirrored, every user in that region reads the same cached tiles. Storage of the coarse global grids on R2 ≈
**$5–30/mo** (coarse = small); serving them is folded into the (a) overlay/readout figures. The recurring cost is
a **monthly GRACE/ERA5 refresh job** (cron, minutes of compute) ≈ **~$5/mo.** → **~$10–35/mo, ~flat across
1k/100k/1M users.**

**DEPENDENCIES** an **org/app Earthdata credential** (replace the personal `~/.edl_token`; this is an
account/ops action, not a build); the (a) TiTiler overlay path to render them; the (c) cache as the storage home.

**UNLOCKS** the honest "your region" context that makes the parcel readout *trustworthy* (the §5 moat: telling
the truth about which signals are your-land vs your-region); the region-context inputs the Pacto trigger and the
donor map reuse.

**CAPITAL TRANCHE** **T1 — non-dilutive grants (NOW).** Pure spine/serving work on free data; no proof-gate
dependency. The org-EDL credential is a free account step.

---

## (c) The per-region / global climatology baseline cache (H3/geohash × month × variable)

**SCOPE** *(GLOBAL_ROLLOUT §4.2 — the scale move).* A gridded cache so **anomalies work anywhere without
re-pulling history per request.** Key = `(coarse cell × month × variable)` where cell = **H3 res 6–7 / geohash**
(~a few km, so neighbors share a normal); value = the **`clim_mean, clim_std`** that `kernel/climatology.py`
already produces, per month per variable (NDVI, CHIRPS/SPI-3, SMAP, …). A readout = point-sample the *current*
value (the (a) fast path) **+ a cache lookup** for the normal → instant z-score, **no per-request multi-year
pull.** Correctness is already global (climatology is AOI-agnostic — GLOBAL_ROLLOUT §4); this is a **cost +
latency** move, not a correctness fix.

**The naive-vs-cached comparison — this IS the ROI argument for (c):**

| | Per-readout work | Latency | Cost @ 1M users (10 lookups/user/mo = 10M readouts) |
|---|---|---|---|
| **NAIVE (no cache)** | point-sample current **+ pull ~3–5 yr monthly history** every time (~150 Range GETs current + **~thousands** for history) | ~tens of seconds | **unaffordable** — ~10M × thousands of GETs + heavy compute → ~$1000s/mo in GET+compute, and not interactive |
| **CACHED (this milestone)** | 1 current point-sample (~150 GETs) **+ 1 KV lookup** | ~2 s | folded into the (a) readout line (~**$900/mo** at 1M) |

Without (c), the readout figures in (a) are off by an order of magnitude and the product is not interactive at
scale. **(c) is what makes the L1 promise "cheap as promised" instead of quietly unaffordable per user.**

**EFFORT** ~**5 dev-weeks** geo-backend: ~2 wk the cache schema + read/write (SQLite/Parquet MVP → R2 KV /
DynamoDB at scale) keyed `cell|month|variable`; ~2 wk the background warmer that builds normals per cell via the
(d) batch path on first-touch + a launch-region pre-warm; ~1 wk wiring the readout to do lookup-then-point-sample
and the "baseline still warming up" honest fallback (GLOBAL_ROLLOUT §4.1, for thin-history cells).

**ONE-TIME $** ~**$20K** labor + **one-time warm compute** for the launch region (see (d)).

**MONTHLY RUN $** — **scales with cells warmed, ~flat in users.** The cache *storage* is tiny: `mean+std × 12
months × ~5 variables` per cell. Storage examples (ESTIMATE): a **launch region** (~50k H3-r7 cells) ≈ a few MB →
**<$1/mo R2**; **every populated land cell on Earth** (H3 r6 ≈ ~1–2M land cells × 60 values) ≈ low-GB → **~$5–25/mo
R2** + KV read costs folded into the readout. On-demand warming of new cells is a **per-cell one-time** cost (see
(d)), not a per-user monthly cost. → **~$1–25/mo, ~flat across 1k/100k/1M users** (it tracks *coverage*, not
traffic).

**DEPENDENCIES** the (d) batch path (the warmer's engine); the (b) mirrored region layers as cache-able
variables; a cell library (H3/geohash).

**UNLOCKS** instant + cheap readouts at any scale (the difference above); pre-warming a new launch region in one
batch job (the M2 "new region = a cache-warm, not a fork" property); the Earthdata multi-tenant fix (b) lands
here as cached values.

**CAPITAL TRANCHE** **T1 — non-dilutive grants (NOW)** for the schema + warmer + a launch-region warm. The
**global pre-warm** (every land cell) is a larger compute spend that fits **T3 (seed)** scale-up — but on-demand
first-touch warming means you never need the global warm before you have users there. Not proof-gated.

---

## (d) The region-batch perf path + caching (the warmer's engine)

**SCOPE** *(GLOBAL_ROLLOUT §2 Fix B + §2 crossover.)* The **batch** read path for region/cell-scale work:
`odc.stac.load` + a **single vectorized `.compute()`** (kill the per-scene python loop), **preserving all three
columns** (`ndvi_mean / ndvi_std / valid_frac`) the kernel and webapp consume — a naive `.mean()` that drops
std/valid_frac is a **regression** (GLOBAL_ROLLOUT §2 Fix B). This path is **not on the user hot path** — it
**warms the (c) cache** and serves internal region pulls (the Pacto trigger over a municipio, the donor/region
overlay). The crossover is explicit (GLOBAL_ROLLOUT §2): parcel → (a) point-sample (interactive); region →
this batch path (cache-warming). `/api/parcel` routes by AOI area (ties to the area cap that finishes M0).

**EFFORT** ~**3 dev-weeks** geo-backend: ~1.5 wk the vectorized reduce + single-`.compute()` rewrite with the
3-column contract + tests; ~1.5 wk the area-routing in `/api/parcel`, the area/date caps (bound unbounded
per-request work, GLOBAL_ROLLOUT §1.3), and the batch-job runner (in-region us-west-2 so requester-pays egress ≈
$0).

**ONE-TIME $** ~**$12K** labor.

**MONTHLY RUN $** — **scales with regions/cells warmed, ~flat in users.** This is **burst compute**, not a
standing service: it runs when warming a region. A launch-region warm (ESTIMATE: ~50k cells × a few years of
coarse + S2 composites) ≈ a **few hundred $ of one-time** us-west-2 spot/Lambda compute (egress ≈ $0 in-region).
Steady-state, on-demand first-touch warming + monthly refresh ≈ **~$10–50/mo** depending on new-coverage rate —
**independent of user count.** → **~$10–50/mo, ~flat across 1k/100k/1M users.**

**DEPENDENCIES** the loaders (DONE, geom-parameterized); the (c) cache as the write target.

**UNLOCKS** the (c) cache (this is its engine); cheap region overlays for the (a)/giving donor map; the M2
"warm a new region's cells" step (each new region/vertical = a config + a warm, per GLOBAL_ROLLOUT M2).

**CAPITAL TRANCHE** **T1 — non-dilutive grants (NOW).** Performance/infra work on the free spine; not
proof-gated. Large multi-region warm campaigns scale with the **T3 seed** (geographic expansion), but per-region
warming is cheap and demand-driven.

---

## (e) UX / productization — accounts, geocoding-at-scale, mobile

**SCOPE** *(GLOBAL_ROLLOUT §1.1 + Phase 2 funnel.)* Turn the validated single-parcel readout into a **product a
stranger can use and return to**: **(i)** geocoding — the MVP uses **Nominatim free tier (rate-capped)**
(GLOBAL_ROLLOUT §1.1); at scale this must move to a paid or self-hosted geocoder; **(ii)** user **accounts**
(save my parcel, history, the funnel for L2/L3/giving); **(iii)** a **mobile** experience (the RESEARCH §4 gap #1
user is phone-only — the zero-knowledge "point at my home" promise). The **marker/draw + geocode + drop the
Honduras `setView` lock + remove `/api/municipios`** pieces are part of finishing M0; the *at-scale* productization
is here.

**EFFORT** ~**8 dev-weeks**: ~3 wk full-stack (accounts/auth, saved parcels, the funnel), ~3 wk frontend/mobile
(responsive/PWA or a thin native shell on MapLibre), ~2 wk the geocoder migration (self-host Nominatim/Photon on
a small box, or wire a paid geocoder behind a cache).

**ONE-TIME $** ~**$32K** labor + **~$0** one-time infra (self-host fits an existing box).

**MONTHLY RUN $** — **scales with users.** Per-user request assumptions ESTIMATE:

| Component | Per-user assumption (ESTIMATE) | 1k | 100k | 1M |
|---|---|---|---|---|
| **Geocoding** | ~2 geocodes/user/mo; self-hosted Nominatim = a small VM (flat) **or** paid ~$0.50/1k | self-host **~$20** (VM) | self-host **~$40** or paid ~**$100** | self-host **~$150** or paid ~**$1,000** |
| **Accounts/API host** | app servers + DB (Postgres) | ~$25 | ~$150 | ~$800 |
| **Auth/email/SMS** | signups + notifications | ~$5 | ~$50 | ~$400 |
| **≈ TOTAL productization** | | **~$50/mo** | **~$240–300/mo** | **~$1,350–2,200/mo** |

Self-hosting the geocoder (a flat VM, not per-call) is the cost-control move at 1M — paid geocoding is the line
that would otherwise dominate.

**DEPENDENCIES** the finished M0 (marker/draw/geocode entry); (a) serving for the map; ideally (c) so saved
parcels load instantly.

**UNLOCKS** the **B2C funnel** (BUILD_PLAN Phase 2 / VISION L1 front door) — accounts are the on-ramp to L2, L3,
and the giving UX, and the retained-user base any **seed** narrative needs; the mobile reach to the actual
target user.

**CAPITAL TRANCHE** **Split.** The geocode/marker/`setView`-removal that **finishes M0** = **T1 (grants, NOW).**
**Accounts + mobile + scaled geocoding = T3 (the $1–3M seed)** — these are the productization you fund *after*
traction and the proof-unlock, when you are converting a working public map into a retained product. (Per EQUITY
doc: sequence dilutive spend after proof so you sell less of the company.)

---

## Roll-up — total cost to finish L1

**ONE-TIME (build):**

| Milestone | Dev-weeks | One-time $ | Tranche |
|---|---|---|---|
| (a) global serving infra | 6 | ~$24K | T1 grants |
| (b) region-context layers + Earthdata fix | 4 | ~$17K | T1 grants |
| (c) climatology baseline cache | 5 | ~$20K | T1 grants |
| (d) region-batch perf path | 3 | ~$12K | T1 grants |
| (e) productization (M0-finish slice) | ~3 of 8 | ~$12K | T1 grants |
| (e) productization (accounts/mobile/scaled geocode) | ~5 of 8 | ~$20K | **T3 seed** |
| **TOTAL** | **~26 dev-wk** | **~$105K** | mostly T1 |

→ **L1 finishes for roughly $85K–$130K one-time** (ESTIMATE; center ~$105K). **~$85K of it is T1 non-dilutive,
pre-proof grant work** (a Stellar/Celo/Gitcoin build award + the $600K grant floor cover it many times over, at
**0% dilution**); only the ~$20K accounts/mobile/scaled-geocode slice waits for the **T3 seed**. **None of L1 is
gated behind the proof-unlock** (mainnet + real disbursement + IDB) — that gate sits on the Phase-1 giving axis,
not on L1 serving.

**MONTHLY RUN (at scale), all milestones combined:**

| | 1k users | 100k users | 1M users |
|---|---|---|---|
| (a) serving (basemap + readout + overlays + storage) | ~$8 | ~$235 | ~$1,940 |
| (b) region layers (geo-scaling, ~flat) | ~$10 | ~$20 | ~$35 |
| (c) climatology cache (geo-scaling, ~flat) | ~$1 | ~$10 | ~$25 |
| (d) batch warm (geo-scaling, ~flat) | ~$10 | ~$30 | ~$50 |
| (e) productization (user-scaling) | ~$50 | ~$280 | ~$1,800 |
| **≈ TOTAL L1 run** | **~$80/mo** | **~$575/mo** | **~$3,850/mo** |

The honest headline: **the full global "see your land" map runs for under ~$600/mo at 100k users and under
~$4k/mo at 1M** — *because* (b)/(c)/(d) are amortized across geography (flat in users) and the readout uses
point-sampling + cache instead of tile rendering (the RESEARCH §5 trap, avoided). At ~$4k/mo for 1M users, L1's
COGS is **fractions of a cent per user/mo** — the "cheap as promised" property is real and quantified.

---

## What $X buys for this layer (the L1 ask)

- **~$25K (a Stellar/Celo build award, T1):** finishes M0 + ships **(a) global serving + (b) region layers** —
  i.e. the basemap on R2, MapLibre, honest "your region" overlays, and the Earthdata multi-tenant fix. The map
  goes from "validated on 3 parcels" to "anyone, anywhere, served cheap." **0% dilution.**
- **~$60K (stack 2–3 T1 grants):** the above **+ (c) the climatology cache + (d) the batch warm** — the readout
  becomes **instant and order-of-magnitude cheaper per user**, and a new launch region is **one warm job, not a
  fork.** This is the complete, scalable L1 *engine*. **Still 0% dilution.**
- **~$85K (the T1 grant ceiling, well inside the $600K floor):** all of the above **+ the M0-finish productization
  slice** (geocode, marker/draw, Honduras lock removed). **L1 is a complete, global, scalable public product** —
  the B2C front door, fully grant-funded, no equity sold, no proof-gate crossed.
- **+~$20K from the T3 seed (post-proof):** accounts + mobile + scaled geocoding — converts the working public map
  into a **retained product with a funnel** into L2/L3/giving. Funded *after* traction so it costs less ownership
  (EQUITY doc sequencing).

**Bottom line:** finishing L1 to a global, scalable consumer product is a **~$85K–$130K one-time** build,
**~$85K of it non-dilutive grant work available NOW** (pre-proof, 0% dilution), running at **<$600/mo at 100k
users / <$4k/mo at 1M** — the cheapest layer in the whole platform, and the one already most-built.

---

*Companion to [GLOBAL_ROLLOUT.md](../GLOBAL_ROLLOUT.md) (the scope this costs), [RESEARCH.md](../RESEARCH.md)
§1/§5 (the unit costs applied), [BUILD_PLAN.md](../BUILD_PLAN.md) (Phase 0/1/2), and the
[strategy/](../../strategy/) capital docs (the tranches). Costs the **finish of L1 only** — L2/L3, giving UX,
[PAID_DATA.md](../PAID_DATA.md), and the Phase-1 proof-unlock are other sections.*
