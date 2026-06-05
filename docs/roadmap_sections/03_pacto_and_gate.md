# Roadmap §03 — Pacto (the giving layer) + crossing the PROOF-UNLOCK gate

*The money-readiness plan for the layer that moves real relief — and the single gate that converts warm
conversations into a priced seed. Builds on [BUILD_PLAN.md](../BUILD_PLAN.md) §1c (Pacto.sol harvest), §3 Phase 1
(the gate sequence), §4 #5 (regulatory shielding); [RESEARCH.md](RESEARCH.md) §6 (giving rails: Celo/Stellar,
GiveDirectly last-mile) + §5 (serving unit costs, applied not re-derived); [GLOBAL_ROLLOUT.md](GLOBAL_ROLLOUT.md)
M0/M1 (the donor map rides the same point-sample + overlay infra); and `strategy/FUNDRAISING_STRATEGY` §4/§8/§9 +
`strategy/EQUITY_AND_DILUTION` (the tranche each milestone draws from). It does **not** re-derive their content —
it costs the steps.*

> **TL;DR.** Phase 0 + Phase 1-on-anvil are *done* (generic `Pacto.sol`, env-driven `DeployPacto.s.sol`,
> `oracle.py`, kernel, L1 first slice — all test-green, the contest PactoSeco live on Mantle Sepolia). What is
> *not* done — and what the **proof-unlock gate** ($0b in BUILD_PLAN) requires — is three things money can't skip:
> **(a)** the generic contract live on a *public mainnet/L2*, **(b)** the oracle running as a *reliable service*
> (not a laptop script), and **(c)** one *real* micro-disbursement through a **licensed local payer** with a
> **counsel opinion letter** in hand first — plus the donor UX (d) that makes it fundable and the UNAH/IDB pilot
> (e) that signs the gate's third clause. Crossing this gate is what re-prices the seed (EQUITY doc: $4M→$10–13M
> post). **Total cash to cross: ~$25K–$70K all-in — dominated by the one-time counsel letter ($10–30K) and pilot
> program money ($6–35K), with code/run cost a few $K; the binding constraints are NON-money** (the licensed-payer
> relationship + counsel turnaround + IDB pilot signature). All of it is funded by the **non-dilutive tranche**,
> before a single share is sold.

---

## 0. Where we actually start (do not re-plan these)

Confirmed against the repo, not assumed:

- **`contracts/src/Pacto.sol`** — the generic, direction-parametric, per-pool-config disbursement primitive
  (`breachBelow` flag, immutable per-pool thresholds, oracle≠owner, pull-payment, monotonic-cycle replay guard).
  Renamed entities done (`pool/cycle/beneficiary/signal`). **Compiles, 22-test port green.**
- **`contracts/script/DeployPacto.s.sol`** — env-driven, *"works unchanged on local anvil AND any real testnet
  RPC."* Proven end-to-end on anvil (`broadcast/.../31337/run-latest.json`). The mainnet step is a *config + funded
  key*, not new code.
- **`oracle/oracle.py`** — the off-chain→on-chain bridge. Posts the raw per-sensor anomaly array; the **contract**
  enforces consensus (`reportDailyMulti … require(inBreach >= minSensorConsensus)`). Proven pushing real 2023
  series → real drought fired → real (mock) USDC claimed, on anvil.
- **L1 first slice** — `ingest/parcel.py` + `app/server.py` (`/api/parcel`) + `app/web/index.html` map, live on
  real NDVI/SAR/landcover for CA/FR/ES parcels.
- **Contest PactoSeco** — live + clickable on **Mantle Sepolia testnet** (a *testnet* deploy; the gate wants
  *mainnet* + a *real* disbursement — see §0b BUILD_PLAN: "nothing yet live on a public *chain*; no *real*
  disbursement").

**So the gate is NOT crossed.** What remains is the five milestones below. The honesty paragraph (BUILD_PLAN §4 #6)
stays verbatim until each clause is literally true.

**Legend.** Each milestone is tagged **[CODE]** (Alex+AI ships it) or **[LEGAL/REL]** (Alex's track — counsel,
country office, payer — money buys time/opinions, not a commit). Costs: **ONE-TIME** = build/setup $; **MONTHLY** =
run $ (given at 1k / 100k / 1M *disbursement-pool users* where the cost actually scales — most of this layer scales
with *pools/transactions*, not L1 map users, so where a number is flat I say so). **TRANCHE** = the funding stage
(`strategy/FUNDRAISING` §4 + EQUITY doc): **T1 = non-dilutive grants to the $600K floor (0% dilution)** ·
**GATE = the proof-unlock itself (no tranche — it's the unlock)** · **T2 = the $1–3M seed, post-unlock**.

---

## (a) Generic Pacto → a public MAINNET / L2  **[CODE]**

The cheapest milestone by far, but it is the *first* clause of the gate ("live on a public mainnet") and must be
done for real, not hand-waved.

- **SCOPE.** Pick a low-fee EVM L2 that has a *real* (mainnet) USDC and a giving story: **Celo** (RESEARCH §6:
  ~$0.01/tx, mobile-first stablecoin rails, the recommended target) — or Base/Optimism if a USD-stable + L2
  presence matters more to a specific grant. Steps: (1) point `DeployPacto.s.sol` at the mainnet RPC + a **funded
  deployer key** (the only new input — code is unchanged); (2) deploy `Pacto` + use the *real* network USDC
  (drop `MockUSDC` for mainnet); (3) **verify the source** on the explorer (the contest learned this is the #1
  credibility item — BUILD_PLAN §5); (4) instantiate one real pool with the drought config + `breachBelow=true`;
  (5) seed it with a small real stablecoin balance so a claim can actually pay out.
- **EFFORT.** **~0.5–1 dev-week** (Alex + AI). The code exists and is anvil-proven; this is RPC config, key
  management, explorer verification, and a deploy dry-run on the L2's own testnet first. *Person: the solo
  builder (Solidity/foundry) — no new hire.*
- **ONE-TIME $.** **~$50–$500 ESTIMATE** — gas on an L2 is cents-to-dollars; the real one-time cost is the **seed
  stablecoin** put into the first pool so a disbursement is non-zero (call it **$200–$2,000 ESTIMATE** of relief
  capital, which is *program money*, ideally donor/grant-funded, not founder cash). Audit is **not** required at
  this scale (see DEPENDENCIES) — the 22-test suite + verified source is the proof artifact for a micro-pilot.
- **MONTHLY $.** **~$0 flat.** A deployed contract has no rent. Per-transaction gas is **~$0.01/tx on Celo**
  (RESEARCH §6) — at 1k / 100k / 1M disbursements/cycle that is **~$10 / ~$1,000 / ~$10,000 per disbursement
  cycle** in gas, *paid from the pool's own funds or a relayer*, not a fixed monthly bill. Oracle posting gas is
  costed in (b).
- **DEPENDENCIES.** Phase 0 (done) + Phase 1 anvil proof (done). A funded deployer key (from `~/Desktop/rhis/
  hunt-keys.env` pattern — fund a fresh key, never reuse). **A formal security audit is NOT a dependency at
  micro-pilot scale** — but it **becomes** one before real money scales past the pilot (budget a **$15K–$40K
  ESTIMATE** audit in T2, not now; flag it so it isn't a surprise).
- **UNLOCKS.** The first clause of the gate ("live on a public chain"). Makes every grant claim
  ("deployed on mainnet, source-verified, anyone can recompute the trigger") literally true. Is the on-chain home
  the oracle (b) writes to and the donor UX (d) reads from.
- **TRANCHE.** **T1.** Trivial cost; this is a direct down-payment on the gate that grants explicitly want to fund
  (Stellar SCF / Celo PG asks in FUNDRAISING §7 are *exactly* "port the trigger onto a public chain"). The seed
  stablecoin is program money — fold it into a grant line item.

---

## (b) Oracle productionization — the Copernicus→contract daemon as a reliable service  **[CODE]**

Today `oracle.py` is a script that runs when Alex runs it. For *real money* to release on a real drought, it must
run unattended, observably, with keys it can't leak. This is the most under-appreciated cost in the whole layer:
**the contract is only as trustworthy as the oracle that feeds it.**

- **SCOPE.** Turn `oracle/oracle.py` into a service: (1) **scheduled ingest** — a cron/worker that, per active
  pool, pulls the day's per-sensor anomalies (NDVI + SPI-3, the proven pair) via the existing loaders and posts
  `reportDailyMulti`; (2) **monitoring + alerting** — liveness ("did today's scene post?"), drift ("oracle's
  off-chain consensus simulation matches the chain's"), and a dead-man's-switch if a pool goes N days without a
  qualifying post; (3) **key management** — the oracle's signing key in a secrets manager / KMS, *separate from*
  the deployer/owner key (the contract already enforces oracle≠owner — honor it operationally); (4) **idempotency
  + replay safety** — never double-post a `dayIndex` (contract guards monotonic cycle, but the daemon must not
  spam reverts); (5) **a recompute log** — persist the public product IDs + anomaly inputs for each post so anyone
  can re-verify (this *is* the audit moat from VISION §3 — make it an artifact, not a promise).
- **EFFORT.** **~2–3 dev-weeks** (Alex + AI). The signal pipeline and the posting call exist; this is the wrapping
  — scheduler, observability, secrets, idempotency, the recompute log. *Person: the solo builder, backend/devops
  hat.* (No SRE hire at this scale; a managed platform does the heavy lifting — see MONTHLY.)
- **ONE-TIME $.** **~$0–$2,000 ESTIMATE.** Mostly time, not cash. Optional: a paid uptime/alerting tier
  (Better Stack / Grafana Cloud free tier covers a pilot) and a secrets manager (free tier on most clouds).
- **MONTHLY $.**
  - **1k users / a handful of pilot pools:** **~$10–$40/mo ESTIMATE** — a single small always-on worker
    (Fly.io/Railway/a $5–10 VPS, or a Lambda/Cloud-Run scheduled function) + free-tier monitoring. The Copernicus
    pulls are $0 data (RESEARCH §1) on the free spine; compute is trivial (one anomaly series per pool per day).
  - **100k users / dozens–hundreds of pools:** **~$50–$200/mo ESTIMATE** — the daemon scales with *number of
    pools/AOIs*, not L1 map users; batch the daily pulls, share a climatology cache (GLOBAL_ROLLOUT §4.2) so
    neighbor pools don't recompute baselines. Add posting **gas** (paid from pools/relayer, ~$0.01/tx Celo).
  - **1M users / thousands of pools:** **~$300–$1,500/mo ESTIMATE** compute+monitoring (a small worker pool +
    queue) — still dominated by *pool count*, not user count. Gas is per-disbursement, costed in (a).
- **DEPENDENCIES.** (a) — there must be a mainnet contract + pool to post to. The loaders (done). A secrets/KMS
  setup.
- **UNLOCKS.** Makes a *real* disbursement (e) trustworthy and unattended — the difference between "we can fire a
  payout if Alex is at his laptop" and "the budget line executes itself." The recompute log makes the
  auditability claim a shippable artifact for funders.
- **TRANCHE.** **T1.** A grant deliverable in its own right (Celo/Stellar "production trigger service"). Cheap;
  high credibility-per-dollar.

---

## (c) The REAL disbursement last-mile — licensed local payer + the counsel opinion letter  **[LEGAL/REL + thin CODE]**

This is the regulatory crux (BUILD_PLAN §4 #5; FUNDRAISING §8). **Tierva is the trigger/oracle/accounting layer —
*when* and *how much*, on-chain, auditable — and is NEVER the custodian.** The fiat to a household is moved by a
**licensed local payer / mobile-money agent / government treasury**; the bank/agent receives a *fiat instruction*
and never touches crypto. This sidesteps US money-transmitter/VASP status and stays clear of Honduras CNBS
003/2024 (which bans supervised FIs from crypto — so **no stablecoin-into-bank design**). "A self-executing line of
a national budget, not a wallet."

- **SCOPE — two parts:**
  - **[LEGAL/REL] The counsel opinion letter (one-time, gating).** A **US-fintech + Honduran counsel** opinion
    that the trigger/accounting-only architecture (Tierva never custodies; a licensed payer moves the fiat) does
    not make Tierva a money transmitter/VASP and complies with CNBS 003/2024. **Required *before any real money
    moves*** (not before the demo — FUNDRAISING §8). This is Alex's track: engage counsel, supply the architecture
    doc, get the letter.
  - **[LEGAL/REL] The licensed-payer relationship (one-time, gating, the true bottleneck).** Sign the entity that
    actually pays the household. Options (RESEARCH §6 last-mile): a **GiveDirectly-style mobile-money operator**
    (~85% reaches recipient), **Kiva-style local Field Partner**, a regional mobile-money agent (Tigo Money /
    similar in Honduras), or (later) the **Stellar Disbursement Platform** (open-source, MoneyGram cash-out ~150
    countries — FUNDRAISING §7 names it as the LAC last mile). For the UNAH pilot the payer is whoever UNAH/COPECO
    can route enrolled-household cash through.
  - **[CODE] The accounting/instruction seam (thin).** The contract emits a *disbursement instruction* event
    (beneficiary, amount, cycle); a small off-chain reconciler turns confirmed on-chain releases into the payer's
    payout file/API call and records the payer's confirmation back against the pool — *accounting only, no
    custody*. **~1–1.5 dev-weeks.** The pull-payment contract already isolates a frozen wallet; this just bridges
    "contract says pay X" → "licensed payer paid X" with a reconciliation record.
- **EFFORT.** Code: **~1–1.5 dev-weeks** (solo builder). Legal/relationship: **weeks-to-months of Alex's
  calendar time**, not dev-weeks — counsel turnaround + payer onboarding/KYC are the long poles.
- **ONE-TIME $.**
  - **Counsel opinion letter: ~$10,000–$30,000 ESTIMATE** (US fintech + Honduran counsel; a scoped opinion, not a
    full regulatory build-out). *This is the single largest one-time line in the whole gate.* Mark ESTIMATE —
    confirm with counsel; a narrowly-scoped memo can land nearer the low end.
  - Payer onboarding/KYC + any setup fee: **~$0–$5,000 ESTIMATE** (often $0 for a pilot via an NGO/Field-Partner
    relationship; an agent network may charge setup).
- **MONTHLY $.** **The transfer itself is cheap; the cost is targeting + cash-out** (RESEARCH §6): mobile-money/
  agent fees + KYC, **not** the on-chain transfer. Expect a **per-payout cash-out fee** (agent margin) rather than
  a fixed monthly — at GiveDirectly's ~85% pass-through, **~15% leakage to last-mile** is the planning number
  (crypto rails push toward ~95%, RESEARCH §6). At 1k / 100k / 1M households this scales **per-payout**, not as
  fixed rent. No fixed monthly for Tierva here (we are not the payer).
- **DEPENDENCIES.** (a) + (b) (a live, oracle-fed pool to disburse from). **(c)'s counsel letter is a hard gate on
  *every* real-money step after it** — nothing real moves until the letter is in hand. The payer signature gates
  the pilot (e).
- **UNLOCKS.** The **second clause of the proof gate** ("one *real* disbursement"). Converts "tested locally, not
  live" into "live with a real disbursement" — the EQUITY-doc valuation lever ($4M→$8–13M post). Also the
  regulatory shield that lets the seed conversation happen without a money-transmitter cloud.
- **TRANCHE.** **T1** (the counsel letter is a textbook non-dilutive line — IDB Lab TA / a grant can fund legal
  diligence for a pilot; FUNDRAISING §9 step 13 explicitly sequences the letter *before* any real-money scale-up).
  The letter is *also* the de-risking artifact that makes T2 priceable.

---

## (d) The donor / giving UX — discover a farmer → fund a pool → watch the data  **[CODE]**

The product face of Pacto, and the thing that makes the layer *fundable* as a consumer/donor experience (RESEARCH
§6 moat: *no consumer "fund a specific farmer and watch the satellite that protects them" product exists*; VISION
§4 "the giving layer rides on all three"). It rides the **same serving infra** as L1/the global rollout — do not
build a parallel stack.

- **SCOPE.** (1) **Discover** — a donor-facing map of enrolled farmers/pools (the deck.gl/MapLibre donor map from
  GLOBAL_ROLLOUT M1), each with its live L1 readout (the *exact data that will fire the payout* — the
  transparency moat); (2) **Fund** — contribute to an earmarked pool (the contract already escrows + pull-pays);
  frame as **anticipatory cash transfer / a gift, not insurance** (RESEARCH §6; no license/underwriter);
  (3) **Watch** — the donor sees the consensus build day-by-day (reuse the L2 explainer-panel seed, BUILD_PLAN
  §1d) and the auto-release event when it fires; (4) **Receipt/transparency** — the recompute log (b) surfaced as
  "here is the public data that moved your gift."
- **EFFORT.** **~3–5 dev-weeks** (solo builder + AI, front-end heavy). It reuses: the existing Leaflet/`/api/
  parcel` readout, the L2 panel seed, the contract's fund/escrow/claim path. New work is the donor flow, the pool
  directory, the fund-contribution UX, and the "watch it fire" timeline.
- **ONE-TIME $.** **~$0–$2,000 ESTIMATE** (dev time; optional design polish). No new data ($0, RESEARCH §1).
- **MONTHLY $.** Rides the **GLOBAL_ROLLOUT §3 / RESEARCH §5 serving math — apply it, don't re-derive**:
  - **1k users:** **~$0–$25/mo ESTIMATE** — MVP needs *no new infra* (point-sample readout in existing FastAPI;
    free Carto/OSM basemap). Effectively the existing app's hosting.
  - **100k users:** **~$30–$150/mo ESTIMATE** — at this point migrate to the M1 serving infra: **PMTiles +
    Protomaps basemap on Cloudflare R2 ≈ $11/mo at 10M tile req** (RESEARCH §5, the 20–300× cheaper path) +
    TiTiler-on-Lambda overlays for the painted donor map (**~$50/M tiles**) + the FastAPI host.
  - **1M users:** **~$150–$800/mo ESTIMATE** — same architecture, more tiles/overlays; R2 zero-egress keeps the
    basemap near-flat; overlays + point-samples scale with active viewers. The point-readout (the L1 promise) is
    the *cheapest op in the stack* and the one most products miss (RESEARCH §5) — keep it off the tile-rendering
    path.
- **DEPENDENCIES.** (a) (a fundable on-chain pool) + (b) (the live data to watch) + GLOBAL_ROLLOUT M0/M1 serving
  infra (the donor map is the same MapLibre + R2 + TiTiler stack). (c) is *not* a hard dependency for the UX to
  exist (donors can fund a pool whose disbursement is pending the payer signature), but a real payout needs (c).
- **UNLOCKS.** The fundraising/adoption story (the transparency moat no charity offers) and the consumer-facing
  proof that the kernel does something a human cares about. Strengthens grant applications (Gitcoin/Celo public
  goods *want* a visible public-good UX).
- **TRANCHE.** **T1** for the MVP donor flow (a grant deliverable + adoption funnel). The full deck.gl donor map
  at scale is a **T2** polish item (it rides M1 infra, which T2 funds anyway).

---

## (e) The UNAH / IDB pilot → a real micro-disbursement  **[LEGAL/REL + integration CODE]**

The third clause of the gate ("IDB pilot signed") and the artifact every seed conversation needs (FUNDRAISING §9
step 10). This is mostly Alex's relationship track, with thin integration code.

- **SCOPE.** **[LEGAL/REL]** Stand up the Honduras pilot with **UNAH (Juan Carlos)** as the in-country research
  anchor and the pathway to **COPECO/SAG** for ground validation + enrollment: name the **municipality cluster**,
  the **trigger setting** (the proven NDVI+SPI-3 consensus config), the **enrollment path**, and the
  **cost-to-first-disbursement**. In parallel, the **IDB country-office relationship** (FUNDRAISING §9 step 4 —
  the long-lead bottleneck, start now) toward a **Discovery/TA grant ($150K–$1M)** framed as "a self-executing
  line of a national budget." **[CODE]** Wire the named cluster as a real Pacto pool (kernel config + cache-warm
  its climatology cells — GLOBAL_ROLLOUT M2; *a config, not a fork*), connect the (c) payer instruction seam, and
  run **one end-to-end real micro-disbursement** to a small set of enrolled households.
- **EFFORT.** Code: **~1–2 dev-weeks** (pool instantiation + cache-warm + payer-seam wiring — most is config on
  built parts). Relationship: **the dominant effort — months of Alex+JC's calendar** (UNAH/COPECO enrollment, IDB
  country-office cultivation). Not dev-weeks; it's the long pole of the entire gate.
- **ONE-TIME $.**
  - **The relief capital actually disbursed** — a *micro* pilot: **~$1,000–$10,000 ESTIMATE** of program money to
    enrolled households (ideally donor/grant/IDB-funded, not founder cash; it is *the payout*, not overhead).
  - **In-country enrollment/validation** (UNAH field time, COPECO coordination, ground-truth): **~$5,000–$25,000
    ESTIMATE** — typically folded into an IDB Discovery/TA grant, not paid out of pocket.
- **MONTHLY $.** **~$0 incremental for Tierva** during the pilot beyond (b)'s oracle run cost (one more pool) and
  per-payout cash-out fees (c). The pilot's recurring cost is *program* (relief + field), grant-funded.
- **DEPENDENCIES.** (a) + (b) + (c) **all required** (live contract, reliable oracle, counsel letter + signed
  payer — you cannot run a *real* disbursement without the licensed payer and the legal opinion). JC's
  co-founder/role status is the cap-table pre-req noted in BUILD_PLAN §6 / EQUITY doc (settle Alex⇄JC split first)
  — *relationship, not money.*
- **UNLOCKS.** The **third and final clause of the proof gate** → the gate is **crossed**. Re-prices the seed
  (EQUITY doc: $2M at 20% instead of 50%). Opens the accredited-host path to Adaptation Fund / GCF (long-horizon,
  via IDB/UNAH) and the T2 SAFE.
- **TRANCHE.** **T1** funds the build + pilot setup (IDB Lab Discovery/TA is itself non-dilutive and *is* the
  pilot money — FUNDRAISING §7 #5). The **gate it crosses** then unlocks **T2** (the $1–3M seed). This milestone
  is the hinge between the two tranches.

---

## What $X + what non-$ unlocks the gate

**The gate (BUILD_PLAN §0b / FUNDRAISING §4) = `live on a public mainnet` + `one real disbursement` + `IDB pilot
signed`.** Mapping the milestones: (a) buys clause 1, (c)+(e) buy clause 2, (e) buys clause 3; (b) makes clause 2
*trustworthy*; (d) makes the whole thing fundable and adopted.

**What the CASH buys (all T1 — non-dilutive, 0% dilution, before any share is sold):**

| Line | Type | One-time $ (ESTIMATE) |
|---|---|---|
| (a) mainnet deploy + verify + seed pool | code/program | $250 – $2,500 |
| (b) oracle productionization | code | $0 – $2,000 |
| (c) **counsel opinion letter** (US + Honduran) | legal | **$10,000 – $30,000** ← largest line |
| (c) payer onboarding/KYC | legal/rel | $0 – $5,000 |
| (d) donor-UX MVP | code | $0 – $2,000 |
| (e) pilot relief capital + enrollment/validation | program | $6,000 – $35,000 |
| **TOTAL one-time to cross the gate** | | **≈ $16K – $77K**, *clustered ~$25K–$70K* |

Plus modest **run cost while crossing**: **~$20–$240/mo** (oracle service + donor-UX hosting at pilot scale) — a
rounding error against the floor. **Audit ($15K–$40K) is deferred to T2**, not part of crossing the gate at
micro-pilot scale.

> **Bottom-line cash range: ~$25K–$70K of non-dilutive T1 money crosses the gate** — well inside the $600K floor,
> and most of it (counsel, pilot capital, enrollment) is exactly what IDB Lab Discovery/TA + the Web3 public-goods
> grants exist to fund. **No equity is sold to cross the gate.**

**What the NON-MONEY unlocks (the real bottlenecks — Alex's track, money can't shortcut these):**

1. **The licensed-payer signature** (c) — the last-mile entity that legally moves the fiat. Without it, no *real*
   disbursement, no matter the budget. Relationship + KYC time.
2. **The counsel opinion letter** (c) — money buys it, but it is *time-gated* (counsel turnaround) and **gates
   every real-money step after it**. Start it early.
3. **The IDB country-office relationship + the UNAH/COPECO enrollment** (e) — the long-lead bottleneck
   (FUNDRAISING §9 step 4: *"relationship lead time is the bottleneck — start before any call opens"*). This is
   the third gate clause and cannot be bought, only cultivated.
4. **The Alex⇄JC founder split** (BUILD_PLAN §6 / EQUITY doc) — cap-table hygiene that must be settled *before*
   the T2 SAFE the gate unlocks; gated on JC's reply, not on money.

**The sequence that makes this cheap (EQUITY doc):** grants (T1) fund all of (a)–(e) at 0% dilution → the gate is
crossed → the seed (T2) prices at $10–13M post instead of $4M → the same $2M costs 20% instead of 50%.
**Sequencing is dilution; this layer is the sequence.**

---

*Sources: [BUILD_PLAN.md](../BUILD_PLAN.md) §1c/§3-Phase1/§4 · [RESEARCH.md](RESEARCH.md) §5/§6 ·
[GLOBAL_ROLLOUT.md](GLOBAL_ROLLOUT.md) M0–M2 · `strategy/FUNDRAISING_STRATEGY.private.md` §4/§7/§8/§9 ·
`strategy/EQUITY_AND_DILUTION.private.md`. Repo state verified 2026-06-04 (`contracts/src/Pacto.sol`,
`contracts/script/DeployPacto.s.sol`, `oracle/oracle.py`, `kernel/`, `ingest/parcel.py`, `app/`). All $ marked
ESTIMATE are planning frames, not quotes — confirm counsel + payer + audit figures before any real-money use.*
