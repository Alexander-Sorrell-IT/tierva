# Tierva — Build Plan (the executable layer)

*The layer **beneath** [VISION.md](VISION.md) and [RESEARCH.md](RESEARCH.md). VISION says **what** Tierva
is; RESEARCH says **what to build it on** (its "Bottom line for the build" — 6 directives — is the spec this
plan executes). This doc says **what we already have, what to lift from Pacto Seco, and in what order** —
grounded in a per-module audit of the contest codebase (`Alexander-Sorrell-IT/pacto-seco`) and the
control/raise constraints in [`../strategy/`](../strategy/).*

> **TL;DR.** The contest built the substrate, not a one-off. The kernel (`dcsi.py`), the data spine
> (12 reuse-as-is loaders), and the disbursement contract (`PactoSeco.sol`) all migrate into Tierva with
> *renaming + parameterization*, not rewrites. The strategy docs resolve the B2C-vs-B2G question as a
> **framing** choice on **one engine**, and prescribe a **kernel-first** build path. So the order is:
> **Phase 0 harvest → cross the proof-unlock gate → wrap with L1/L2/L3.** Capital and build are interlocked —
> each grant funds the proof step that unlocks the next tranche.

---

## 0. The two things that set the whole sequence

**(a) The fork is not a build fork.** The strategy docs (`PITCH_2048`, `GLOBAL_IDEA_AND_RAISE`, `FUNDRAISING`)
deliberately keep **one substrate under two names**: *Pacto Seco* = the B2G / parametric-public-finance / impact
framing (grant funders + IDB); *Tierva* = the B2C / commercial Earth-intelligence framing (the only pitch put in
the 2048 room). There is **one documented build path: kernel-first** — because the *same* kernel proof is the
universal capital gate for **both** framings. The B2C "front door" (L1 SEE) is the already-built funnel + the
VC-facing wrapper, **not** a separate track to build first. → *Don't agonize over the fork; build the kernel.*

**(b) The proof-unlock gate is the critical path.** A single gate converts warm conversations into a priced seed:
**live on a public *mainnet* + one *real* disbursement + IDB pilot signed.** It is **not crossed today** (we have:
testnet deploy + real-2023 backtest + 22-test contract on anvil). Everything dilutive waits on this gate; only
**non-dilutive grants** + a **$250–750K 2048 Fast-Track** are honestly available now. **The build work that crosses
this gate IS the roadmap below.**

---

## 1. The harvest manifest — what to lift from Pacto Seco

Audit lens: **reuse-as-is** (domain-agnostic, lift verbatim minus the `__main__` demo) · **generalize**
(useful but Honduras/drought-coupled — parameterize) · **leave-behind** (contest-only). Source repo:
`projects/copernicuslac-seguridad-alimentaria-2026/pacto-seco/`.

### 1a. THE KERNEL (domain-agnostic core — `generalize`, the highest-value lift)

| Asset | What it is | To generalize |
|---|---|---|
| `src/pacto_seco/index/dcsi.py` | The consensus engine: raw values → z-score anomalies vs climatology → fuse → count sources agreeing past threshold → fire only when **≥N agree continuously for a persistence window with gap tolerance**. Already parametrizes `sensors / threshold / min_sensors / weights / persistence_days / max_gap_days`. | **(1)** Comparator is hardwired `<= threshold` ("drier") in 3 places → make **direction/`breach()` a parameter** so the same kernel fires for flood/too-wet, heat/too-hot, any L3 metric. **(2)** De-hardcode `SENSOR_COLS` (drought menu) → caller-supplied set. **(3)** Move drought constants (`THRESH=-1.2`, `PERSISTENCE_DAYS=20`…) into a **config object**, not module defaults. **(4)** Rename `dcsi`/`drought` → `signal`/`breach`. The `monthly_climatology` / anomaly z-score logic is reusable **as-is** — and it doubles as L3's "what's normal for your land" machinery. **Effort: M.** |
| `tools/pc_scanner.py` | No-auth STAC catalog inventory — discovers which EO collections are free/ingestable, tagged by signal axis. | **reuse-as-is** → `kernel/catalog.py`. The tool that tells L1 what it can ingest. **Effort: S.** |
| *(extract from `backtest/`)* | Hidden inside the proof scripts is a repeated **AOI-agnostic validation harness**: resolve AOI → pull each sensor → anomaly → run single-sensor **vs** N-sensor consensus → first-trigger-date → summary table + grid plot. | Parametrize AOI list, sensor set, baseline/test split, threshold/direction (inherit from kernel). Becomes the **kernel-calibration / regression harness** — proves a trigger config won't false-fire *before money is wired to it*. **Effort: M.** |

### 1b. THE DATA SPINE — L1 SEE (`reuse-as-is`, the largest win by volume)

12 of 16 loaders lift cleanly: each splits a **geom-parameterized, globally-valid `*_timeseries` pull** (keep)
from a **drought-coded `*_anomaly` z-score** (push the anomaly step *into the kernel* so every vertical reuses it).
The only Honduras coupling is in the `__main__` demos — **drop them on lift.**

**Three shared access patterns → promote to `kernel/access/` (reused across many loaders):**
- **Planetary Computer STAC, no-auth** — `sentinel_loader`, `sar_loader`, `modis_vi`, `modis_lst`, `cropland`, `fapar`
- **NASA Earthdata bearer + CMR granule** — `smap_loader`, `grace_loader` *(token at `~/.edl_token`, valid to 2026-07-29)*
- **Copernicus CDS key bootstrap** (`setup_cdsapirc`) — `era5_loader`, `et_loader`, `ccism_loader`, `cgls_fapar_loader`

**⚠️ The resolution truth that governs the "look at MY land" promise** (RESEARCH §1 confirmed in code):

| Can resolve a single parcel (≤10–20 m) | Field-to-region (250–300 m) | **Region-only context** (1 km → 300 km) |
|---|---|---|
| **Sentinel-2** NDVI (10 m) · **Sentinel-1 SAR** (10–20 m) · **WorldCover cropland** (10 m) | MODIS-VI (250 m) · CGLS-FAPAR (300 m) | SMAP/ERA5/ET (~9 km) · MODIS-LST (1 km) · CHIRPS (~5 km) · GOES (~10 km) · ccism (~25 km) · **GRACE (~300 km, monthly)** |

→ **L1's per-parcel view rides on the three 10-m sources.** Everything else is honestly labelled a *regional
context layer* — never rendered as "your field." This is the engineering expression of the VISION honesty rule.

**Generalize (4 loaders, not as-is):**
- `ccism_loader.py` — `BBOX_PAD=0.4°` silently averages ~40 km of neighbors; expose per-call, label region-only.
- `goes_loader.py` — `DEFAULT_HOUR_UTC=19` (Honduras noon) + `noaa-goes16` (Americas-only). Globalize: derive hour from longitude, pick satellite by region (GOES-E/W, Himawari, Meteosat).
- `fapar_loader.py` — superseded by `cgls_fapar` (project's own docstring); lift only if a coarse global FPAR fallback is wanted.
- `enso_loader.py` — a global *scalar* index (no geometry) → not a map tile; route to **L2/L3** as a macro climate-context / leading-indicator signal.

### 1c. PACTO — the giving / disbursement layer

| Asset | Classify | Action |
|---|---|---|
| `contracts/src/PactoSeco.sol` | **generalize** | A **generic consensus-gated disbursement primitive**, not a drought thing. Keep all security mechanics (oracle≠owner separation, on-chain run-span counting, gap/confirmation guards, pull-payment so a frozen wallet can't block the pool, monotonic-cycle replay guard, sweep-only-unreserved). Change: move hardcoded `constant`s → **per-pool immutable config**; rename `municipio→pool`, `season→cycle`, `household→beneficiary`, `DCSI→signal`; add **direction** so flood/heat pools work. **Effort: M.** |
| `contracts/src/MockUSDC.sol` | **reuse-as-is** | 6-decimal ERC-20 test token w/ blacklist toggle (tests pull-payment survives a frozen beneficiary). Migrates verbatim. **Effort: S.** |

### 1d. THE WEBAPP — splits three ways (don't migrate as one blob)

- **L1 map shell** (`server.py` `/api/municipios` + Leaflet/GeoJSON + per-AOI `/api/dcsi` chart) → **generalize**: token-free map foundation; swap Honduras polygons for user AOIs/parcels, de-hardcode baseline years + Spanish copy.
- **L2 explainer** (`/api/sensors` panel + monthly z-score strip viz + `tools/build_sensor_panel.py`) → **generalize**: this is the *seed of L2 UNDERSTAND* — per-signal "why the system concluded X" with trigger/corroborator roles. Replace static notes with AI-generated explanation; keep the strip layout.
- **Payout theater** (20-household animation, lempiras, "11 minutes") → **leave-behind** (contest demo).

### 1e. LEAVE BEHIND (contest/Honduras-coupled)

`data/__init__.py` (empty) · `municipios/honduras_dry_corridor.py` (GADM + Dry-Corridor filter) · the
**`backtest/` suite as shipped** (2023 El Niño proofs, hardcoded JC targets — *but extract the harness, §1a*) ·
`enso_leadtime.py` (drought lead-time — *noted as the conceptual seed for L3 forecasting*) · all video/asset
tooling (`make_thumbnail`, `build_trailer*`, `shot_panel.js`, `transcribe_vo`, `ccism_targeted`).

---

## 2. Target Tierva layout (where the harvest lands)

```
tierva/
  kernel/                      # domain-agnostic, fork-independent  ← Phase 0
    consensus.py               # ← dcsi.py, direction-parametric "N-of-M breach + persist + gap → fire"
    climatology.py             # ← the monthly-baseline z-score engine (also L3's "normal for your land")
    backtest.py                # ← generalized single-vs-consensus validation harness
    catalog.py                 # ← tools/pc_scanner.py — discover ingestable EO collections
    access/                    # ← 3 shared access patterns promoted out of the loaders
      planetary_computer.py    #    no-auth STAC
      earthdata.py             #    CMR + bearer
      cds.py                   #    setup_cdsapirc
  ingest/sources/              # L1 data spine — raw *_timeseries pulls (anomaly step removed → kernel)
    sentinel2.py  sentinel1_sar.py  worldcover_cropland.py     # PARCEL-CAPABLE (10 m)
    modis_ndvi.py  cgls_fapar.py                               # field-to-region
    smap.py era5_rain.py et.py chirps.py modis_lst.py
    ccism.py grace.py goes_lst.py enso.py                      # regional context
  contracts/
    Pacto.sol  MockUSDC.sol    # ← consensus-gated disbursement primitive + test token
  app/
    api/                       # ← FastAPI: L1 map endpoints + L2 explainer
    web/                       # ← Leaflet (MVP) → MapLibre + PMTiles later (RESEARCH §5)
```

---

## 3. The roadmap (kernel-first, gated by capital & proof)

### Phase 0 — Harvest into the kernel *(fork-independent, low-regret, start now)*
Lift §1a–1c into the `tierva/` tree above. **Done when:** `kernel/consensus.py` fires direction-agnostically with
a passing port of the contract's 22 tests; the 3 parcel-capable loaders + 3 access modules run against a
user-supplied AOI (not a Honduras municipio); `Pacto.sol` compiles with per-pool config + renamed entities. *No
capital or fork decision required — needed under either framing.*

### Phase 1 — Cross the PROOF-UNLOCK gate *(the critical path; this is what unlocks the seed)*
Per `FUNDRAISING §9` (weeks 6–10): **testnet → public mainnet/L2 → one *real* micro-disbursement → stand up the
UNAH/Honduras pilot.** Two hard gates inside this phase (see §4): the real disbursement must route through a
**licensed local payer** (never direct-to-bank), and a **US-fintech + Honduran counsel opinion letter** must be in
hand *before any real money moves*. **Crossing this gate = live mainnet + 1 real disbursement + IDB pilot signed.**

### Phase 2 — Wrap as the consumer platform (the B2C funnel + monetization tiers)
- **L1 SEE** — *mostly built.* Package the parcel-capable spine, go global (drop Honduras AOIs), serve cheap from object storage (R2 + TiTiler + COG point-sampling per parcel — RESEARCH §5), MapLibre + PMTiles basemap.
- **L2 UNDERSTAND** — wrap the explainer-panel seed (§1d) with an AI interpreter + 40-yr Landsat history + seasonal forecast (Farmer.Chat-style RAG advisor — RESEARCH §3). ENSO loader feeds this.
- **L3 THE GARDENER** — wrap **FAO GAEZ v5** (free per-pixel 70-crop suitability now-vs-2080), downscale/fuse with 10-m Sentinel embeddings + the land's real history → plain-language "grow X, switch by year N." *The moat is the fusion, not the climate model* (RESEARCH §2). `enso_leadtime.py` is the conceptual seed.
- **Pacto giving UX** — donor discovers a farmer, funds an earmarked pool, watches the live satellite data that fires the auto-release. Premium-data adapters (Satellogic parcel close-ups, SAR all-weather) are the honest upsell where the free spine fails.

> Phase 2's *sequencing* is the only thing the B2C-vs-B2G lean touches — and even then it's about which tier to
> monetize first, not whether to build the kernel. Default: lead with L1 (funnel) per Alex's B2C lean.

---

## 4. Constraints that GATE the order *(from `strategy/`, non-negotiable)*

1. **Founder control through seed.** SAFE with **no board/control terms**; grants-first to the **$600K floor at 0%
   dilution**; right-size 2048 ($250–750K Fast-Track now, **or** $2M lead *only* at the proof-unlock at ~$10–13M
   post); co-founder equity from the **founder pool, before investors**. → **Founder split locked before any share
   is sold;** size every check against *cumulative* dilution (two 20% rounds = 64% kept).
2. **JC = titled co-founder *with* equity, NOT co-controller.** Required for 2048 (founder-market-fit "rests on
   JC"). Equity from the founder pool, sized so Alex keeps board control. The Jun-4 outreach **left terms open** —
   nothing promised beyond "titled co-founder, terms TBD." → **Settle the Alex⇄JC split FIRST, while the cap table
   is clean, before formally pitching 2048.** *(This is the #1 pre-pitch checklist item — gated on JC's reply.)*
3. **Two-track capital — never merge.** DE C-corp (PBC) = project/IP/founder salary/grants/SAFE, QSBS-eligible, the
   *only* equity vehicle. NM LLC = infra/hardware ($3M+ CapEx), asset-financed, **kept entirely out of the equity
   room.** *(Overrides the old `GUARANTEED_BLUEPRINT` "$230K compute moat to VCs" idea — that violates the split.)*
4. **Proof-unlock gate** (§0b) — **not crossed today.** Only grants + Fast-Track available now; the $2M term-sheet
   ask fires only *at* the unlock. First contact with 2048 can open now (pre-proof is their lane).
5. **Regulatory shielding.** Tierva is the trigger/oracle/accounting layer — *when & how much*, on-chain, auditable;
   the **fiat is moved by a licensed local payer / mobile-money agent / treasury**, never custodied by us ("a
   self-executing line of a national budget, not a wallet"). Honduras CNBS 003/2024 bans supervised FIs from
   crypto → **no stablecoin-into-bank design.** Counsel opinion required *before* real money (not before the demo).
6. **Honesty rule (load-bearing).** Keep the verbatim paragraph in every funder touch: *"2-sensor consensus proven
   on real 2023 data; 22-test contract proven locally on anvil; nothing yet live on a public chain; no real
   disbursement; IDB is a channel we're walking, not a deal we've closed."* Claims escalate only as proof crosses
   gates ($150–750K grant ceiling now; $1–3M seed only post-unlock). Vision (kernel at civilization scale) vs ask
   (a wedge: LAC drought + IDB pilot) — never conflate. Impact vocabulary → grant room only; data-platform/data-moat
   vocabulary → the *only* framing in the 2048 room.

**Raise order (governing):** grants-first (Stellar/Gitcoin/Celo/Mercy Corps + start the slow IDB Lab relationship)
→ open 2048 pre-proof but hold the term-sheet ask → **proof-unlock** → form/confirm the single DE PBC + $1–3M
post-money SAFE → long-horizon Adaptation Fund / GCF via an accredited host. Each grant funds the proof step that
unlocks the next tranche — **build and capital are interlocked.**

---

## 5. Contest — what's left (Pacto Seco, Jun 11) *(separate track, all finalist-gated)*

Submission is **complete** (video live + Jun-7 gate met; contract live on testnet + clickable; endorsement +
honest description on the page). Remaining is pitch-day polish, only if named finalist on **Jun 10**:
- **Verify the contract source on mantlescan** — highest-leverage credibility item; turns "click to verify" into readable, verified Solidity.
- **JC sign-off** on `PITCH.es.md` + any local Corredor Seco data to add *(awaiting his reply)*.
- **Rehearse the 3-min pitch** — JC narrates (Spanish), Alex drives the screen + clicks the live contract at the Jan-vs-Jul beat.
- **Jun 10** finalist notification → **Jun 11** final.

> Note: the Jun-11 demo is **ammo, not a gate** — it produces the "live on a public chain + real-data backtest"
> traction that 2048 wants, but the *capital* gate is the mainnet + real-disbursement + IDB proof-unlock (§0b).

---

## 6. The one decision actually open

Not the fork (resolved: one engine, kernel-first, B2C is the wrapper). The live decision is **JC's reply → the
Alex⇄JC founder split** (constraint #2) — it's the top pre-pitch item and gates the clean cap table. Everything in
**Phase 0 is independent of it** and can start immediately.

---

*Sources: per-module audit of `pacto-seco` (loaders, `dcsi.py`, `PactoSeco.sol`, webapp, tools) + `strategy/`
(control, equity/dilution, two-track capital, proof-unlock, regulatory, honesty). Companion to
[VISION.md](VISION.md) and [RESEARCH.md](RESEARCH.md).*
