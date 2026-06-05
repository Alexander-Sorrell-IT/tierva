# Tierva — Master Roadmap (money-ready)

*The single capital-sequenced plan for finishing the **whole** idea. It sits on top of the executable docs —
[VISION](VISION.md) (what), [RESEARCH](RESEARCH.md) (what to build on), [BUILD_PLAN](BUILD_PLAN.md) (the phases +
constraints), [GLOBAL_ROLLOUT](GLOBAL_ROLLOUT.md), [PAID_DATA](PAID_DATA.md), [TEST_PLAN](TEST_PLAN.md) — and the
deep-costing in [`roadmap_sections/`](roadmap_sections/). **Purpose: when money lands, this is "execute the plan,"
not "make one." Every milestone carries a cost and the funding stage that pays for it.***

> All dollar figures are **ESTIMATE**, costed at *market hire-out rates* (1 dev-week ≈ $4K) so a tranche
> underwrites the work honestly — Alex executes solo+AI, so real cash burn is a fraction. Capital tranches are the
> ones in `strategy/` (FUNDRAISING + EQUITY_AND_DILUTION): **T1 = non-dilutive grants to the $600K floor (0%
> dilution, available NOW)** · **the PROOF-UNLOCK gate (a milestone, not money)** · **T2 = the $1–3M seed
> (post-gate, dilutive)**.

---

## 0. Where we start (already done — sunk, not re-costed)

The **engine is built and proven**, so this roadmap costs the *finish*, not the start:

- **Phase 0 — harvest:** `kernel/consensus.py` (direction-agnostic), generic `Pacto.sol` per-pool contract,
  `ingest/` data spine. Test-green, committed.
- **Phase 1 — proof spine:** `DeployPacto.s.sol` + `oracle.py`, proven end-to-end on local anvil.
- **M0 — L1 first slice:** `ingest/parcel.py` + `/api/parcel` + the map UI, **live-validated** (real NDVI/SAR/
  landcover for parcels in California, France, Spain). Contest `PactoSeco` is live on Mantle Sepolia testnet.

**The hard part — the kernel that reads the world and the contract that pays itself — exists and works.** What's
left is *productizing* it (L1→L2→L3 + giving) and *crossing the capital gate*.

---

## 1. The shape of the plan: two axes, one capital sequence

The work runs on **two independent axes** that share one funding ladder:

- **Axis A — the consumer product:** L1 SEE → L2 UNDERSTAND → L3 GARDENER (+ paid-data upsell). The B2C front
  door and revenue engine.
- **Axis B — the giving + proof-unlock gate:** generic Pacto on mainnet → real disbursement (licensed payer +
  counsel) → IDB pilot. This is what **re-prices the seed** (EQUITY doc: ~$4M → $10–13M post).

**They don't block each other.** L1 is grant-funded public-good work; the gate is a separate, mostly-legal track.
Crossing the gate is what unlocks the seed that funds L2/L3.

---

## 2. The master cost map (every milestone, one table)

| # | Milestone | Axis | One-time build (ESTIMATE) | Run @100k users | Tranche | Code / Legal |
|---|---|---|---|---|---|---|
| L1 | **Finish "see your land"** — global serving (R2/PMTiles/TiTiler), region-context layers + Earthdata multi-tenant fix, climatology cache, batch perf, M0-finish UX | A | **~$85K** (+~$20K accounts/mobile at seed) | ~$575/mo | **T1 grants** | Code |
| G | **Cross the proof-unlock gate** — generic Pacto→mainnet, oracle-as-service, real disbursement via licensed payer **+ counsel opinion letter**, donor UX, UNAH/IDB micro-pilot | B | **~$25–70K** (mostly the $10–30K counsel letter + $6–35K pilot program money; code ~few $K) | ~$50–200/mo (oracle) | **T1 grants** | Mostly Legal/Rel |
| L2 | **UNDERSTAND** — AI explainer + 40-yr Landsat history + seasonal forecast (wrap, don't train) | A | **~$25–35K** | ~$60–90/mo | **T2 seed** (or Fast-Track) | Code |
| L3 | **THE GARDENER** — wrap FAO GAEZ v5 (free) + per-parcel downscale/fusion + plain-language 20-yr crop call | A | **~$50–80K** ($20–30K core + $30–50K premium fusion) | ~$60–120/mo | **T2 seed** | Code |
| P | **Paid-data upsell** — Satellogic sub-meter close-ups + rapid SAR, same adapter interface | A | **~$30K** (~2 dev-months) | $0 standing (variable COGS only, ~$4.50/km²) | **T2 seed** | Code |
| — | **Giving UX + oracle prod + mainnet** (folded into G) | B | ~$5–10K | — | T1 | Code |

**Totals:** the full platform is **~$220–290K of one-time build/legal work** — of which **~$110–155K is T1
(grants, 0% dilution, available now)** = finish L1 + cross the gate; and **~$110–145K is T2 (post-gate seed)** =
L2 + L3 + paid.

---

## 3. The capital → milestone map (the headline)

### 💵 Tranche A — non-dilutive grants → the $600K floor *(0% dilution, available NOW, pre-proof)*
*Sources (FUNDRAISING §7): Stellar Community Fund, Gitcoin, Celo Public Goods, Mercy Corps Crypto for Good, IDB
Lab Discovery/TA. Grants raise the proof (making later equity cost less) and keep you 2048-Fast-Track-eligible.*

**Buys, in order:**
1. **Finish L1** (~$85K) → "see your land" is a global, scalable public map. *0% dilution.*
2. **Cross the proof-unlock gate** (~$25–70K, dominated by the counsel letter + pilot program money) → generic
   Pacto live on mainnet + one real disbursement through a licensed payer + the IDB/UNAH pilot.
3. **A small team for ~a year** — Founder + JC (in-country) + 1 geospatial/backend eng ≈ **~$27K/mo (~$320K/yr)**.

→ **A ~$400–600K grant stack funds finishing L1 + crossing the gate + a year of the small team — at 0% dilution.**
The binding constraints here are **not money** — they're the licensed-payer signature, counsel turnaround, and
the IDB/UNAH relationship (Alex's track).

### 🔓 The PROOF-UNLOCK gate *(a milestone, not money)*
Live mainnet + one real disbursement + IDB pilot signed. **This is what re-prices the seed** (EQUITY: $4M →
$10–13M post). Everything below waits on it — so you sell far less of the company.

### 💵 Tranche B — the $1–3M seed *(post-money SAFE, DE C-corp, AFTER the gate)*
**Buys the premium product + the team to run it:**
- **L2 UNDERSTAND** (~$30K) + **L3 GARDENER** (~$65K) + **paid-data** (~$30K) — the monetizing tiers.
- **The medium team** — + frontend eng + ML/agronomy + fractional ops/legal.
- **L1 productization** (accounts, mobile, scaled geocoding, ~$20K).

→ **A $1–3M seed completes the full L1→L2→L3 + giving + paid platform with a real team.** Per the EQUITY doc,
sequencing this *after* the gate keeps Alex's controlling stake (right-sized check at the re-priced valuation).

### 🏗️ Track B — infrastructure ($3M+ CapEx, NM LLC) — *a separate rail, never in the burn*
The land + data-center asset play is **asset-financed in the NM LLC**, leases compute to the C-corp. It does
**not** touch the operating cap table or the burn above. (Kept out per the two-track rule, BUILD_PLAN §4 #3.)

---

## 4. The run-cost reality (why this stays cheap)

The whole platform's cloud opex, applied bottom-up from RESEARCH §5 (point-sampling + caching, *not* tile
rendering — the named cost trap, avoided):

| | 1k users | 100k users | 1M users |
|---|---|---|---|
| L1 (serving + region + cache + UX) | ~$80/mo | ~$575/mo | ~$3,850/mo |
| L2 (explainer, cache-amortized LLM) | ~$5–10 | ~$60–90 | ~$300–500 |
| L3 (GAEZ host + downscale + narration) | ~$10–20 | ~$60–120 | ~$250–600 |
| Pacto oracle (per pools, not users) | ~$10–40 | ~$50–200 | ~$300–1,500 |
| **≈ TOTAL** | **~$110–150/mo** | **~$750–1,000/mo** | **~$4.7–6.5k/mo** |

**The entire platform runs for ~$1k/mo at 100k users** — COGS is fractions of a cent per user. The "cheap as
promised" property is real and quantified, because L2/L3 inference and the region layers are **cache-amortized
across geography**, not paid per user.

---

## 5. Bottom line (the money-ready answer)

- **The engine is done and proven.** What's left is productization + crossing one gate.
- **~$110–155K of grant-stage work (0% dilution, fundable now) finishes L1 and crosses the proof-unlock gate** —
  the binding constraints are relationships/legal, not money.
- **A $1–3M seed, taken *after* the gate re-prices it, completes L2 + L3 + paid + the team** — the full platform.
- **It runs for ~$1k/mo at 100k users.**

So when money arrives, finishing is mechanical: **grants → L1 + gate; seed → L2/L3/paid/team.** Each dollar maps
to a finished piece, and the riskiest part (does the kernel actually work?) is already answered: *yes, on real
data, on-chain.*

---

*Detail per layer: [`roadmap_sections/01_L1_finish.md`](roadmap_sections/01_L1_finish.md),
[`02_L2_L3.md`](roadmap_sections/02_L2_L3.md), [`03_pacto_and_gate.md`](roadmap_sections/03_pacto_and_gate.md),
[`04_paid_team_capital.md`](roadmap_sections/04_paid_team_capital.md).*
