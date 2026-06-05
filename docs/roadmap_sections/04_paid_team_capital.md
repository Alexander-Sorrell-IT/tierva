# 04 — Paid-Data Integration, Team, Burn & the Capital→Milestone Map

*The money-readiness **capstone input**. Builds on — does not re-derive — [PAID_DATA.md](../PAID_DATA.md)
(the premium adapter design), [RESEARCH.md](../RESEARCH.md) §1 (web-verified data unit costs) + §5 (serving
unit costs), [GLOBAL_ROLLOUT.md](../GLOBAL_ROLLOUT.md) (M0/M1/M2), [BUILD_PLAN.md](../BUILD_PLAN.md)
(Phase 0/1/2), [VISION.md](../VISION.md) (L1/L2/L3 + giving), and the strategy set
`strategy/FUNDRAISING_STRATEGY`, `strategy/EQUITY_AND_DILUTION`, `strategy/GLOBAL_IDEA_AND_RAISE` (the raise
mechanics). It costs PART A (paid data) and PART B (team + burn + capital sequence), then reconciles the two
against the milestones from sections 01–03.*

> **How to read the milestone references.** Sections 01–03 (data/serving · kernel/proof · L2/L3/giving) are
> being written in parallel; this section refers to every milestone by its **canonical name** — *Phase 0/1/2*
> (BUILD_PLAN), *M0/M1/M2* (GLOBAL_ROLLOUT), *L1/L2/L3 + giving-UX* (VISION), and *the proof-unlock gate* — never
> by a sibling section's numbering, so the mapping survives whatever numbering 01–03 land on.

> **The unit costs below are carried, not re-looked-up.** Every $/km², $/scene, and $/M-tile figure is the
> web-verified value from RESEARCH §1 (data) and §5 (serving), applied here. New numbers (salaries, dev-weeks,
> total burn) are tagged **ESTIMATE**.

---

## §0 — Start from reality: what is ALREADY DONE (the plan starts here, not at zero)

The capital map only funds **remaining** work. The following is built, test-green, and committed — **$0 of
every tranche is needed for it:**

| Already done | Evidence | What it means for the capital map |
|---|---|---|
| **Phase 0 harvest** — `kernel/consensus.py` (direction-agnostic N-of-M breach+persist), `kernel/climatology.py`, generic `contracts/src/Pacto.sol` per-pool primitive, `ingest/` spine (3 access modules + 8 source loaders) | repo `kernel/`, `contracts/src/`, `ingest/` | The kernel + spine are sunk cost. **Grant tranche funds the gap above them, not them.** |
| **Phase 1 (anvil)** — `DeployPacto.s.sol` + `oracle/` proven end-to-end on local anvil | repo `contracts/`, `oracle/` | Proof-unlock is *half-crossed*: the mechanism works; only **public-mainnet + real disbursement + IDB pilot** remain (Phase 1-remaining below). |
| **M0 L1 first slice** — `ingest/parcel.py` + `app/server.py` (`/api/parcel`) + `app/web/index.html` map, **live-validated** on real NDVI/SAR/landcover for California / France / Spain parcels | repo `app/`, `ingest/parcel.py` | The MVP read path *exists and works*. M0-remaining is the global-serving + region-context + cache + perf-batch finish, not a from-scratch build. |
| **Contest PactoSeco** live on Mantle Sepolia testnet (clickable) | contest submission | Testnet proof is in hand; it is **ammo, not the gate** (BUILD_PLAN §5). |

**NOT yet built (everything the tranches below fund):** rest of M0 L1 (global serving infra, region-context
layers, per-region climatology cache, perf batch path), all of M1 + M2, L2, L3, the giving-UX, the **paid-data
adapters (PART A)**, and the proof-unlock remainder (mainnet + real disbursement + IDB pilot + counsel letter).

---

# PART A — Costing the paid-data integration

*Builds directly on [PAID_DATA.md](../PAID_DATA.md). That doc designed the adapter (the `ImageryProvider`
protocol, the resolver, the RED LINE, the vendor order). This part **prices** it: build effort, the per-km²
pass-through economics, and how it maps to revenue/tiers. It does not re-summarize the design.*

## A.1 — Build effort (the premium adapter behind the same interface)

PAID_DATA §1C is explicit that the premium tier is **3 new files + a resolver + a small per-source split** — not
a second pipeline. Costing that scope:

| Build unit (per PAID_DATA §1C / §5) | Scope | EFFORT (dev-weeks · who) | ONE-TIME build $ |
|---|---|---|---|
| `ingest/access/_provider.py` | the `ImageryProvider` Protocol + `Price`/`OrderHandle` + `FreeStacProvider` (free providers implement paid methods trivially) | **0.5 wk** · geospatial/backend eng | folded into the eng salary (see PART B) |
| Per-source split (`sentinel2`, `sentinel1_sar`) | extract `_ndvi_from_items` / `_sar_from_items` helper + render-only `*_render` entry, keep `*_timeseries` free-pinned (the §1A refactor that makes the RED LINE structural) | **1.0 wk** · geospatial/backend eng | — |
| `ingest/resolver.py` | the free-vs-paid escalation logic + `quote()` billing seam + `authorize()` credit gate (PAID_DATA §2/§4) | **1.0 wk** · geospatial/backend eng | — |
| `ingest/access/satellogic.py` — **vendor #1** | sub-meter optical archive/tasking adapter; STAC-best-case reuses the NDVI math; fallback = thin COG-download front (PAID_DATA §5) | **1.5–2.5 wk** · geospatial/backend eng | — |
| `ingest/access/sar_paid.py` — **vendor #2** | ICEYE/Capella/Umbra rapid-tasking SAR adapter; reuses the GRD vv/vh read path; quote-required → `Blocked` | **1.5–2.5 wk** · geospatial/backend eng | — |
| Credits/billing wiring | pre-purchased-credit ledger + SaaS charge on the **commercial (PBC) side only** — never the relief rail (PAID_DATA §4 hard rule) | **1.0–1.5 wk** · backend eng (+ a few days of the same eng for Stripe/credits UI hooks) | payment-processor fees are %-of-revenue, not a build line |

- **Vendor #1 (Satellogic) total: ~4–5 dev-weeks.** **Vendor #2 (SAR) total: ~3–4 dev-weeks** *after* #1 (reuses
  the resolver + protocol). Combined **~7–9 dev-weeks of the geospatial/backend eng** — about **2 dev-months**.
- **DEPENDENCIES:** the per-source split depends on the M0 parcel read path (DONE) and the M1 batch path being
  stable; the credits/billing wiring depends on the **DE C-corp existing** (commercial side) and on L3 existing if
  bundled (A.3). The resolver depends on nothing new.
- **UNLOCKS:** the parcel close-up that the free 10 m spine *cannot* render (RESEARCH §1 moat ①) and the
  faster/finer all-weather event look (moat ②) — i.e. the only honest paid surface in the product.
- **CAPITAL TRANCHE: the $1–3M seed** (Track A, DE C-corp). Paid adapters are a **monetization** feature; they
  sit in M2 (GLOBAL_ROLLOUT) and are funded *after* the proof-unlock, alongside L2/L3/giving-UX — not by grants.
- **STANDING MONTHLY RUN: $0.** This is build-only code; it incurs **no fixed monthly opex**. Its cost is the
  variable pass-through below (A.2), which only fires when a user actually orders.

## A.2 — The per-km² pass-through economics (variable COGS, NOT fixed opex)

The defining property: paid imagery is **variable cost of goods, billed per order** — `vendor $/km² × area ×
margin` (PAID_DATA §4). It never appears as a standing monthly run-cost line; it scales **only with paid orders**,
and `authorize()` debits pre-purchased credits **before** any `order()` spends, so a self-serve API can never run
an unbounded bill (PAID_DATA §4).

Cost basis carried verbatim from RESEARCH §1C (web-verified 2026-06-04 — list figures, **not contracted quotes**;
re-confirm against a live account per PAID_DATA §6):

| Vendor / mode | Cost basis (RESEARCH §1C) | Unit | What a typical order costs (ESTIMATE) |
|---|---|---|---|
| **Satellogic — archive** | **~$4.50/km²** | per km² | a ~1-acre parcel ≈ 0.004 km² → vendor cost is **sub-cent**; even a 1 km² close-up = **~$4.50** |
| **Satellogic — tasking** | **~$12/km²** | per km² | 1 km² tasked = **~$12** |
| **Umbra SAR (priced fallback)** | **$675–4,750 / scene** | per scene | a single rapid-tasking scene = **$675–$4,750** — event-driven, high-ticket |
| ICEYE / Capella SAR | **quote-required** | per scene | resolver returns `Blocked` rather than guess (PAID_DATA §2/§5) |
| *(deferred)* Maxar 30 cm | ~$15–60/km² (reseller-gated) | per km² | premium step above Satellogic when 30 cm specifically required |
| *(deferred)* Planet AUM | ~€665 / 500 ha / yr | area subscription | doesn't fit per-km² credits → managed-area tier later |

**The economics that make this safe and profitable:**
- **Satellogic archive is almost free at parcel scale.** A smallholder's plot is ~0.004 km², so the vendor cost
  of *the exact upsell the product exists to sell* (the parcel close-up) is a fraction of a cent. The price the
  user pays is dominated by **margin + a minimum credit unit**, not raw vendor cost — high gross margin by
  construction.
- **SAR is the opposite: high-ticket, event-driven.** $675–$4,750/scene means rapid SAR is a **donor/relief-org
  account feature or a per-event diagnostic spend**, never a casual self-serve click. Margin is thinner in % but
  the absolute ticket is large.
- **Margin is TBD (commercial-side decision)** but the *shape* is: charge `vendor $/km² × area × margin`;
  pre-paid credits cap exposure; the §3 RED LINE keeps all of this **out of the on-chain trigger path** (paid
  pixels are consumer/diagnostic only, never a kernel sensor).

## A.3 — How it maps to revenue / tiers (the upsell where the free spine fails)

Mapping per PAID_DATA §4 (tier mapping) and VISION §4 (L1/L2/L3):

| Tier | Data cost | Paid-data role | Money flow |
|---|---|---|---|
| **L1 SEE** | **$0** (free spine only) | none — never silently bills | — |
| **Parcel close-up** | Satellogic pass-through (A.2) | **one-off credit spend** *or* **bundled into the L3 Gardener subscription** (the "look at MY exact land" promise is L3's, and where sub-meter pays for itself) | SaaS charge → vendor pass-through, **DE PBC commercial side** |
| **SAR / event look** | Umbra/ICEYE pass-through (A.2) | **event-driven** credit spend or a relief-org/donor account feature; **diagnostic-only** (RED LINE) | commercial side; **never** the relief rail |

**The hard rule that PART A must never break (PAID_DATA §4):** premium-imagery billing and the relief-pool
disbursement are **two money-flows that never touch.** Relief-pool funds never buy tasking; premium billing never
rides the disbursement rails. This keeps the giving layer clean and the kernel auditable.

**Revenue framing:** the paid tier is **upside on L3**, not a standalone line. L3 Gardener (subscription) is the
home; the parcel close-up is the feature that makes "your exact land" literally true at sub-meter; SAR is the
relief-org/donor add-on. So PART A's revenue **rides the L3 + giving milestones**, which is why it is seed-funded
alongside them (PART B).

---

# PART B — Team, burn & the capital→milestone map (the money-readiness capstone)

*This is the load-bearing part: the explicit reconciliation of **who you hire as money arrives**, **what the burn
is**, and **which tranche funds which milestone** from sections 01–03. Builds on `strategy/FUNDRAISING_STRATEGY`
(the funder list + comp-anchored ranges), `strategy/EQUITY_AND_DILUTION` (the $600K floor + dilution table), and
`strategy/GLOBAL_IDEA_AND_RAISE` (the two-track capital model). It does not re-derive those; it **applies** them
to the build.*

## B.1 — The master serving-cost table (Track A cloud opex — applied from RESEARCH §5, not re-derived)

Every "MONTHLY RUN $" in the milestone blocks below references **this one table**, so the numbers can never
silently diverge. These are **Track A cloud opex** (DE C-corp). Track B self-hosting (NM LLC, §B.5) is the
eventual alternative, noted but never merged into burn.

| Serving component (RESEARCH §5) | Unit cost basis | @ 1k users | @ 100k users | @ 1M users (ESTIMATE) |
|---|---|---|---|---|
| **Basemap** — PMTiles+Protomaps on Cloudflare R2 (zero egress), MapLibre HTTP-Range | **$11 / 10M tile req** (vs ~$120 S3, ~$3,600 Google) | **<$1** | ~**$11** | ~**$110** |
| **Raster overlays** — TiTiler-on-Lambda over free S2 COGs | **~$50 / M tiles** (vs Mapbox ~$250) | **~$5** | ~**$50** | ~**$250–500** |
| **Per-location readout** — COG point-sample (`rio-tiler /point`, ~150 concurrent Range reads/parcel) | compute-bound; **co-locate in-region to zero AWS requester-pays egress** (RESEARCH §1) | **~$20–50** (1 small always-on box) | ~**$300–800** (autoscale) | **~$3k–8k** (the dominant line) |
| **Geocoder** — Nominatim free tier (MVP) → self-host / paid at scale | free MVP; self-host ~$50–150/mo at scale | **$0** | ~**$50** | ~**$150–300** |
| **API/app compute + DB** — FastAPI + climatology cache (Parquet/SQLite → KV) | small box → autoscale + R2/Dynamo KV | **~$30–60** | ~**$300–600** | ~**$2k–5k** |
| **TOTAL Track-A cloud opex** | | **~$55–110 / mo** | **~$700–1,500 / mo** | **~$5.5k–14k / mo** |

**The punchline (RESEARCH §5, applied):** serving from object storage instead of managed tiles is a **20–300×
cost reduction** — the difference between L1 being "cheap as promised" and quietly unaffordable. At 1M users the
**dominant line is point-sample compute, not tiles** — which is *why* RESEARCH §1's "co-locate compute in-region
to zero requester-pays egress" is the load-bearing serving decision. The 1M column is **ESTIMATE** (extrapolated
from §5 unit costs; re-measure before relying on it). **Paid-data COGS (PART A) are deliberately absent here** —
they are variable per-order pass-through, not standing opex.

## B.2 — The team: who to hire as money arrives

Roles sequenced to the tranche that can afford them. Salaries are **ESTIMATE** (US/remote-blended, deep-tech
pre-seed/seed bands; fully-loaded ≈ 1.25× base for payroll/benefits/tools).

| Role | Fully-loaded $/yr (ESTIMATE) | $/mo (ESTIMATE) | Hired at which tranche | Why / what they build |
|---|---|---|---|---|
| **Founder (Alex)** | ~**$90k–120k** | ~**$8–10k** | grant floor (Track A salary, GLOBAL_IDEA §7) | architecture, all of Phase 1-remaining + M0/M1 build |
| **Co-founder (JC, UNAH)** | equity-led + stipend ~**$30–60k** | ~**$2.5–5k** | grant floor (in-country) | the IDB/COPECO/SAG path, ground validation, the pilot — *titled co-founder, founder pool, terms TBD* (BUILD_PLAN §4 #2) |
| **Geospatial / backend eng #1** | ~**$140k–180k** | ~**$12–15k** | grant floor (the one early hire) | M0-remaining global serving + M1 perf/cache + **the PART A paid adapters** |
| **Frontend eng** | ~**$130k–170k** | ~**$11–14k** | **seed** | MapLibre migration, the giving-UX donor map, L2/L3 consumer surfaces |
| **ML / agronomy person** | ~**$150k–190k** | ~**$13–16k** | **seed** | L2 AI interpreter (Farmer.Chat-style RAG) + L3 GAEZ-fusion gardener (RESEARCH §2/§3) |
| **Ops / legal (fractional → FT)** | fractional ~**$40k**; FT ~**$120k** | ~**$3.5k** → **$10k** | **seed** (fractional can start at gate) | the **counsel opinion letter** (a Phase-1 gate), entity/cap-table, regulatory shielding, IDB contracting |

**Two team shapes:**
- **Small team (grant-funded):** Founder + JC + 1 geospatial/backend eng. **Burn ≈ $22.5k–30k/mo** (salaries) +
  ~$0.1–1.5k/mo cloud (B.1, depending on user scale during build) ≈ **~$23k–31k/mo**, call it **~$27k/mo center
  ESTIMATE**, **~$320k/yr**.
- **Medium team (seed-funded):** the above **+** frontend eng **+** ML/agronomy **+** fractional ops/legal. **Burn
  ≈ $52k–63k/mo** (salaries) + cloud (B.1, growing with users) ≈ **~$55–70k/mo**, call it **~$60k/mo center
  ESTIMATE**, **~$720k/yr**.

## B.3 — The capital sequence → milestone map (the headline)

The capital sequence is fixed by the strategy set: **non-dilutive grants → the $600K floor → the proof-unlock
gate → the $1–3M seed**, with **Track B infra ($3M+ CapEx) on a separate rail that never merges into the burn.**
The map below assigns **every remaining milestone from sections 01–03** to the tranche that funds it.

### Tranche A — Non-dilutive grants → the $600K floor (0% dilution, DE C-corp)

- **Amount / instrument:** **$150K–$750K**, stacked from Stellar SCF ($15–150K), Gitcoin (next round, $100–200K
  pools), Celo PG/Climate Collective (≤~$50K), Mercy Corps Crypto-for-Good (≤$100K equity-free), IDB Lab
  Discovery ($150K–$1M) — captured into the **DE C-corp**, **0% dilution** (`EQUITY_AND_DILUTION` recommended
  sequence; `FUNDRAISING §6–7`). Target: **clear the $600K floor** (`EQUITY_AND_DILUTION`).
- **What it funds (the SMALL team, B.2):** Founder + JC + 1 geospatial/backend eng.
- **Milestones it completes (sections 01–03):**
  1. **Phase 1-remaining** — testnet → **public mainnet/L2** + **one real micro-disbursement** through a licensed
     local payer + the **US-fintech + Honduran counsel opinion letter** + stand up the UNAH/Honduras pilot
     design. *This is the work that crosses the proof-unlock gate* (BUILD_PLAN §0b, FUNDRAISING §9 wk 6–10).
  2. **M0-remaining** — finish global L1: `sentinel2`/`era5_rain` geom-hash cache keys, the region-context layers,
     the parcel area/date caps, the §5 UI honesty contract (GLOBAL_ROLLOUT M0).
  3. **M1** — cheap & instant at scale: vectorized batch path, the gridded climatology cache, PMTiles+R2 basemap +
     MapLibre migration, TiTiler overlays (GLOBAL_ROLLOUT M1).
- **Net result (the headline claim):** **with the grant tranche you finish L1-global (M0+M1) AND cross the
  proof-unlock gate.** L1 is the free spine, $0 data cost — the grant buys the *engineering + the proof*, not data.
- **Runway check (B.4 proves it):** $600K ÷ ~$27k/mo small-team burn ≈ **22 months** — comfortably longer than
  the time to finish Phase 1-remaining + M0 + M1.

### The PROOF-UNLOCK GATE (a milestone, NOT a tranche)

**Live on a public mainnet + one real disbursement + IDB pilot signed** (BUILD_PLAN §0b, FUNDRAISING §3,
GLOBAL_IDEA §9). Crossing it is funded by Tranche A; it **prices the seed** — each proof milestone bumps the
valuation, so the seed sells *less* of the company for the same dollars (`EQUITY_AND_DILUTION`: $2M post-proof at
$10M = 20% vs 50% pre-proof). **The grant→seed seam sits between M1 and M2.**

### Tranche B — The $1–3M seed (post-money SAFE, DE C-corp, AFTER the gate)

- **Amount / instrument:** **$1M–$3M** ($1–2M center, $3M stretch — `FUNDRAISING §4`, `GLOBAL_IDEA §9`), **post-
  money SAFE** into the DE C-corp at a proof-supported **~$10–13M post** (2048 Ventures' 15–20% target,
  `EQUITY_AND_DILUTION`). Dilutive — but priced *after* proof, so founder keeps **~80%+**.
- **What it funds (the MEDIUM team, B.2):** + frontend eng + ML/agronomy + fractional→FT ops/legal.
- **Milestones it completes (sections 01–03):**
  1. **M2** — new regions & verticals (kernel config + cache-warm), incl. first non-Honduras drought region.
  2. **L2 UNDERSTAND** — AI interpreter + 40-yr Landsat history + seasonal forecast (RESEARCH §3).
  3. **L3 THE GARDENER** — GAEZ v5 fusion → 20-yr "what to grow" (RESEARCH §2).
  4. **Giving-UX** — donor discovers a farmer, funds an earmarked pool, watches the live data that fires the
     auto-release (VISION §4 giving layer).
  5. **PART A paid adapters** — Satellogic parcel close-up (#1) then rapid SAR (#2), monetizing L3 + giving.
- **Net result (the headline claim):** **with the seed you build L2/L3 + the giving-UX + the paid tier, and hire
  the team to do it.**
- **Runway check (B.4):** $1.5M (mid) ÷ ~$60k/mo medium-team burn ≈ **25 months** — covers M2 + L2 + L3 +
  giving-UX + the ~2 dev-months of paid adapters.

### Track B — Infrastructure ($3M+ CapEx, NM LLC, a SEPARATE rail — never in the burn)

Land + data centers, **asset/infra-financed against the asset** in the **NM LLC**, kept entirely out of the
equity room and out of every burn/runway line above (`GLOBAL_IDEA §7`, `EQUITY_AND_DILUTION` cap-table hygiene,
BUILD_PLAN §4 #3). It is the **eventual self-host alternative** to the Track-A cloud opex in B.1 — the C-corp is
its anchor tenant. **Mentioned for completeness; it funds no team, no opex, no milestone above.** Merging it would
sink both rails (a funder sees "data center" in a pilot ask; an infra lender sees a pre-revenue pilot).

## B.4 — The reconciliation (the equation the whole capstone exists to make true)

The capstone's core claim is not three separate tables — it is **one relation that must hold**:

> **tranche $ ÷ monthly burn = runway months ≥ time to build the milestones that tranche funds.**

| Tranche | $ (strategy figure) | Team / burn (B.2) | Runway | Milestones it must fund | Holds? |
|---|---|---|---|---|---|
| **Grants → $600K floor** | $600K (floor); $150–750K range | small, **~$27k/mo** | **~22 mo** | Phase 1-remaining + M0 + M1 (≈ 9–14 build-months ESTIMATE) | ✅ runway ≫ build time |
| **Seed** | $1–2M center ($3M stretch) | medium, **~$60k/mo** | **~17 mo @ $1M · ~25 mo @ $1.5M · ~33 mo @ $2M** | M2 + L2 + L3 + giving-UX + paid adapters (≈ 12–20 build-months ESTIMATE) | ✅ at $1.5M+; **tight at $1M** — raise toward center |
| **Track B infra** | $3M+ CapEx | — (separate rail) | n/a (asset-financed) | none above — leases compute to Track A | ✅ never merged |

**The one caveat the relation surfaces:** a **$1M** seed at ~$60k/mo medium-team burn is ~17 months — workable
but tight against the full M2+L2+L3+giving+paid scope; the **$1.5–2M center** is the honest target, exactly as
`FUNDRAISING §4` frames it ("$1–2M is the realistic center; $3M is the stretch"). The reliable thing here is the
**relation**, not the exact dollar/month — every salary and build-month is **ESTIMATE**; re-anchor to actuals
before any funder-facing use. What is *not* an estimate is the structure: **grants finish L1-global and cross the
gate; the seed builds L2/L3 + paid + the team; Track B never touches either.**

## B.5 — Honesty bound (the house voice)

- **Paid data (PART A) is design-only** — no Satellogic/ICEYE/Umbra account exists, no paid pull has run, every
  price is a RESEARCH §1C list figure, **not a contracted quote** (PAID_DATA §6). The per-km² economics above are
  cost-basis planning, not a priced product.
- **Salaries, dev-weeks, total burn, and the 1M-user cloud column are ESTIMATE** — comp/role-band derivations and
  §5 extrapolations, not quotes or measured load.
- **The capital figures are NOT invented** — $600K floor, 0% grant dilution, $1–3M seed ($1–2M center) are taken
  verbatim from `strategy/EQUITY_AND_DILUTION`, `strategy/FUNDRAISING_STRATEGY`, and
  `strategy/GLOBAL_IDEA_AND_RAISE`; this section only *maps* them onto milestones, it does not re-price the raise.
- **The proof-unlock gate is real and uncrossed** — live mainnet + one real disbursement + IDB pilot signed
  (BUILD_PLAN §0b). No tranche buys proof; Tranche A's *work* crosses it.

---

*Companion to [PAID_DATA.md](../PAID_DATA.md) (the adapter design PART A prices), [GLOBAL_ROLLOUT.md](../GLOBAL_ROLLOUT.md)
+ [BUILD_PLAN.md](../BUILD_PLAN.md) (the milestones PART B funds), [RESEARCH.md](../RESEARCH.md) §1/§5 (the unit
costs applied throughout), and the `strategy/` set (the capital sequence mapped, not re-derived).*
