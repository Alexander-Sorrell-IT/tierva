# Tierva — Paid-Data Integration (the premium imagery upsell)

*The executable layer for incorporating PAID satellite APIs. Builds **on** [RESEARCH.md](RESEARCH.md) §1C
(the web-verified premium-vendor matrix + pricing) and the existing free access layer
(`ingest/access/`, `ingest/sources/`). It does **not** re-summarize the vendor table — it designs the
**integration**: the adapter shape, the trigger logic, the billing model, the vendor order, and an explicit
honesty bound.*

> **DESIGN-ONLY — read this first.** Nothing here has been run against a live paid API. There is no Satellogic,
> Planet, Maxar, Umbra, ICEYE or Capella account, and no real money has moved. Every price is carried verbatim
> from RESEARCH §1C (web-verified 2026-06-04), **not** a real quote. This mirrors the loader docstrings'
> "NOT yet validated against live data" rule — see §6 for the load-bearing unverified assumptions to confirm
> *when an account exists.*

---

## §0 — The one-line frame

Paid satellites are **not a parallel stack.** They are **another adapter** behind the same source-level contract
the free spine already satisfies — slotted in *exactly* where the free 10 m spine fails the parcel test:

| Free spine fails when… | The honest paid fix | Cheapest vendor |
|---|---|---|
| **Resolution** — 10 m Sentinel-2 cannot resolve a ~1-acre plot (~63 m across = a smeared pixel) | sub-meter **parcel close-up** | **Satellogic** (~$4.50/km² archive) |
| **Revisit / latency** — optical may have no recent cloud-free scene over *this* parcel *this week* | high-revisit / on-demand **tasking** | Planet (3 m daily) / Satellogic tasking |
| **Cloud at the moment of an event** — a same-day flood/storm read | **rapid-tasking SAR** (sub-meter, cloud-piercing) | ICEYE / Capella (quote) / Umbra ($675–4,750/scene) |

**One correction that governs §2–§3 (load-bearing):** the free spine is **already all-weather**. Sentinel-1 SAR
(`ingest/sources/sentinel1_sar.py`) pierces cloud for free. So paid SAR's marginal value is **resolution +
revisit latency**, *not* the all-weather property. Anywhere this doc (or the task brief) says "charge for
all-weather," read it as "charge for **finer / faster** all-weather" — the free C-band SAR already sees through
the cloud; you pay only when 10–20 m or a multi-day revisit isn't good enough.

---

## §1 — The adapter interface (free spine = default; paid = the same source contract, swapped in)

### §1A — What "the same interface" actually means (and what it does not)

The three modules in `ingest/access/` do **not** share a function signature — and the paid adapter must not
pretend they do. They share a **role**:

| access module | bootstrap | search | fetch |
|---|---|---|---|
| `planetary_computer.py` | none (no-auth) | `search(collections, geom, …) → [signed items]` | caller reads `item.assets[…].href` |
| `earthdata.py` | `read_token()` | `cmr_search(params) → [entry]` | `download(url, token, dest)` |
| `cds.py` | `setup_cdsapirc(key)` | (in-loader `cdsapi.Client().retrieve`) | (writes file) |

Three different shapes. The **uniform contract the rest of Tierva consumes is one level up, at the *source*
loader**: every `ingest/sources/*.py` exposes

```python
def <signal>_timeseries(geom, start, end, …) -> pd.DataFrame   # tidy, geom-parameterized, globally valid
```

— e.g. `sentinel2.ndvi_timeseries(geom, start, end) → [date, ndvi_mean, ndvi_std, valid_frac]`,
`sentinel1_sar.sar_timeseries(geom, start, end) → [date, vv_db, vh_db]`. **That** is the swappable seam, not
the access layer. So the paid adapter conforms at **two boundaries**:

1. **Down-stream (the source math is reused verbatim):** the adapter must hand back the *same primitives the
   existing source loaders already consume* — signed COG hrefs / an `odc.stac`-loadable item list with the bands
   the math needs (`B04`/`B08`/`SCL` for NDVI; `vv`/`vh` for backscatter). If a paid provider does that, the
   **same NDVI / dB math** that backs `sentinel2.ndvi_timeseries` and `sentinel1_sar.sar_timeseries` runs on the
   paid pixels — only the search/fetch front is swapped. This is the real reuse win; do not duplicate the math.
   **But reuse the math without reusing the entry point** — see the boxed refactor below, which is what makes the
   §3 RED LINE structurally true.

> **Refactor that keeps the RED LINE structural (§3), not just stated.** Today `sentinel2.py` does
> `from ..access.planetary_computer import search` — the free spine is hardwired in, which is *correct* and must
> stay so for the entry point `consensus.py` calls. To reuse the math on paid pixels without opening a path into
> the kernel, split each parcel-capable source into two layers: **(a)** a provider-agnostic internal helper
> (`_ndvi_from_items(items, geom, …)`, `_sar_from_items(items, geom, …)`) holding only the band math; **(b)** the
> consensus-facing entry (`ndvi_timeseries`, `sar_timeseries`) that imports the **free** search directly, as
> today, and is the *only* function the kernel imports. The resolver (§2) calls a **separate, render-only** entry
> (`ndvi_render(geom, provider)`) that feeds *any* provider's items into the same `_ndvi_from_items` helper. So the
> math is shared once; the **free entry stays pinned to the free search**; and a paid provider has no route into
> the kernel because it is reachable only through the render entry, which `consensus.py` never imports. "No path
> into consensus" then holds by construction — not by pretending the sources are inherently free.
2. **The access role (auth + search + fetch)** — the new `ingest/access/<vendor>.py` fills the same role as the
   three above, in whatever shape the vendor's API forces (key bootstrap like CDS; bearer like Earthdata;
   STAC-search like Planetary Computer).

### §1B — Why paid is NOT a literal drop-in: the order lifecycle

Free access is **synchronous**: search → read → return, in one call, for $0. Paid adds a lifecycle free never
has — **quote → authorize → order → poll → deliver** — because (a) it costs `area × $/km²` so spend must be
*authorized before it happens*, and (b) **tasking** is asynchronous (the satellite has to fly over; hours to
days). That asymmetry is the design content. Model it as a small `ImageryProvider` protocol where the free
providers implement the paid-only methods *trivially*:

```python
# ingest/access/_provider.py  (the shared protocol — DESIGN sketch, not yet wired)
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Price:
    usd: float            # area_km2 * usd_per_km2 (+ scene minimums); 0.0 for free providers
    area_km2: float
    mode: str             # "archive" | "tasking" | "rapid-tasking"
    eta_hours: float      # 0 for archive/free; hours→days for tasking

@dataclass(frozen=True)
class OrderHandle:
    provider: str
    order_id: str         # for free providers: a synthetic id resolved immediately
    status: str           # "ready" | "pending" | "failed"

class ImageryProvider(Protocol):
    name: str
    # search returns the SAME signed-item / href primitives the source math consumes
    def search(self, geom, start: str, end: str, **q) -> list: ...
    # paid-only lifecycle; free providers implement quote()->Price(usd=0) and
    # order()-> immediately-ready handle, so callers can treat all providers alike:
    def quote(self, geom, mode: str = "archive") -> Price: ...
    def order(self, geom, start: str, end: str, mode: str = "archive") -> OrderHandle: ...
    def poll(self, handle: OrderHandle) -> OrderHandle: ...
    def fetch(self, handle: OrderHandle) -> list: ...   # -> signed items/hrefs (source-consumable)
```

- **Free providers** (a thin `FreeStacProvider` wrapping `access.planetary_computer.search`): `quote → Price(usd=0,
  mode="archive", eta_hours=0)`; `order → OrderHandle(status="ready")` synchronously; `poll → unchanged`;
  `fetch → search`. So "same interface, swapped in" becomes **literally true at `search()`**, while the paid
  lifecycle is honestly carried by `quote/order/poll`.
- **Paid providers** (e.g. `SatellogicProvider`): `quote` prices the AOI; `order` either resolves immediately
  (archive hit) or returns `status="pending"` (tasking) with a real `eta_hours`; `poll` checks the order;
  `fetch` returns signed COG hrefs the existing NDVI/SAR math reads.
- **`quote()` is the billing seam** (§4) and the **resolver's decision input** (§2): nothing is ordered until a
  `Price` is returned and authorized.

### §1C — Where the files land (extends the BUILD_PLAN layout, does not fork it)

```
ingest/
  access/
    planetary_computer.py   # free  (exists)
    earthdata.py            # free  (exists)
    cds.py                  # free  (exists)
    _provider.py            # NEW — the ImageryProvider Protocol + Price/OrderHandle + FreeStacProvider
    satellogic.py           # NEW — paid adapter #1 (sub-meter archive/tasking)   [§5]
    sar_paid.py             # NEW — paid adapter #2 (ICEYE/Capella/Umbra rapid SAR) [§5]
  sources/
    sentinel2.py            # ndvi_timeseries (free-pinned, kernel-facing) + _ndvi_from_items + ndvi_render
    sentinel1_sar.py        # sar_timeseries  (free-pinned, kernel-facing) + _sar_from_items  + sar_render
  resolver.py               # NEW — the trigger/escalation logic (§2): pick free vs paid provider
```

The source loaders gain an internal math helper + a render-only entry (§1A box) but the **kernel-facing
`*_timeseries` functions stay free-pinned and behaviorally unchanged.** The premium tier is **3 new files** plus
a resolver and that small per-source split — not a second pipeline.

---

## §2 — The trigger: when does Tierva reach for paid?

A single `ingest/resolver.py` decides, per request, whether the free spine suffices or a paid provider is
needed. It reaches for paid only when **the free read is blocked AND the latency of the paid option is
acceptable for the use** (RESEARCH §1C moat ① ②; the access conventions in §1).

```python
# ingest/resolver.py — DESIGN sketch
def resolve_imagery(geom, start, end, *, need_resolution_m, deadline_hours, budget,
                    need_optical=True):
    free = FreeStacProvider()                      # Sentinel-2 / Sentinel-1, $0
    # GATE — is the FREE spine adequate across all three axes? Only when ALL hold:
    #   (a) RESOLUTION: 10 m is fine for this AOI (a ~1-acre plot ~63 m across is a
    #       smeared pixel at 10 m → sub-10 m is the upsell case);
    #   (b) AVAILABILITY: a usable free scene exists within the deadline — either a
    #       cloud-free Sentinel-2 read, or (cloud / no-clear-pass) free Sentinel-1
    #       SAR if SAR satisfies the need (anomaly/data, NOT a human OPTICAL picture);
    #   (c) LATENCY: the soonest usable free scene lands within deadline_hours
    #       (free revisit is ~5 d optical / ~6 d SAR — a same-day need fails this).
    res_ok = need_resolution_m >= 10
    s2 = free.search(geom, start, end, query={"eo:cloud_cover": {"lt": 60}})
    free_usable = (s2 if (s2 and need_optical)              # clear optical exists, OR
                   else free.search(geom, start, end,        # free SAR covers a non-
                                    collections=["sentinel-1-grd"]))  # optical need
    latency_ok = soonest_scene_eta(free_usable) <= deadline_hours
    if res_ok and free_usable and latency_ok:
        return free                                # free is honest here; do NOT upsell
    # Free fails an axis (sub-10 m wanted, OR no usable scene, OR too slow). Consider paid.
    paid = pick_paid_provider(need_resolution_m, deadline_hours)   # Satellogic | SAR (§5)
    price = paid.quote(geom, mode=mode_for(deadline_hours))
    if price.eta_hours > deadline_hours:           # tasking too slow for this need
        return Blocked(reason="no paid option fast enough", best_free=free_usable)
    if not authorize(budget, price):               # §4 — pre-authorized credits / SaaS charge
        return Blocked(reason="not authorized", quote=price)
    return paid
```

The three concrete reach-for-paid moments (each maps to a tier in §4):

1. **User requests a parcel close-up the free tier can't render** (resolution gate). A 1-acre plot is a smeared
   pixel at 10 m → offer the Satellogic sub-meter close-up. **One-off premium** or **bundled into L3** (§4).
2. **Cloud / no recent revisit blocks a needed read** (availability + latency gate). Split by *modality*:
   for an anomaly/data need, **cloud alone never justifies paid** — free Sentinel-1 SAR (all-weather, $0) covers
   it. Paid fires only when (a) a **human-viewable OPTICAL picture** is wanted before the next clear Sentinel-2
   pass (SAR is not an optical look), **or** (b) the need is **sooner than free revisit** (~5 d optical / ~6 d
   SAR) at acceptable resolution → offer Satellogic/Planet tasking **if** the deadline tolerates the ETA, else
   honestly return `Blocked` with the best available free scene.
3. **An event needs a faster / finer all-weather look than free C-band SAR gives** (event gate). Sentinel-1 is
   *already* free and all-weather but is 10–20 m on a ~6-day revisit; when a same-day, sub-meter flood/storm read
   is wanted, escalate to rapid-tasking SAR (ICEYE/Capella). **Event-driven, donor/diagnostic-facing only —
   never the contract input (§3, RED LINE).**

**Latency governs the choice (RESEARCH §1C):** archive = immediate but may not exist for *this* parcel/date;
tasking = hours-to-days; rapid-tasking = the only mode fast enough for a same-day event, and quote-only. A
2-day task is useless for a same-day need — the resolver must `Blocked` rather than silently buy a too-slow
order.

---

## §3 — RED LINE: paid data MUST NOT enter the on-chain trigger path

This is a hard constraint, not a preference. VISION §3 enshrines as a *proven* kernel property: every input is
**"recomputable from public IDs; no commercial oracle; falsifiable by anyone."** The Sentinel-1 loader was
deliberately chosen on the free, no-auth `sentinel-1-grd` collection (not the account-gated RTC) **precisely to
stay auditable.** If a paid ICEYE/Satellogic scene ever fired a disbursement, nobody could recompute the trigger
without paying for that scene — **the audit moat breaks, and the kernel's headline claim becomes false.**

Therefore:

- **The auditable on-chain trigger stays 100% on the free, recomputable spine** — Sentinel-2 NDVI + free
  Sentinel-1 SAR (already all-weather) → `kernel/consensus.py`. The "flood/trigger needs all-weather
  confirmation" requirement is met by **free Sentinel-1**, not by paid SAR. The task brief's phrasing invites
  conflating these; do not.
- **Paid imagery is the CONSUMER / DIAGNOSTIC layer only** — the donor's "see the flood over this farm," the
  user's parcel close-up, an L2 explainer illustration. Human-facing pixels, never a contract input.
- **If paid ever corroborates an event, it is a human-readable overlay, not a kernel sensor.** It can sit *beside*
  the auditable trigger in the UI ("here is a sharper picture of what the free, recomputable consensus already
  fired on"), but it is excluded from `consensus.py`'s sensor set by construction.

Enforcement is structural (the §1A boxed refactor is what makes it so): paid providers live in
`ingest/access/{satellogic,sar_paid}.py` and are reachable only through `resolver.resolve_imagery` for the
**render-only** source entries (`*_render(geom, provider)`). The kernel imports only the **free-pinned** consensus
entries (`ndvi_timeseries`, `sar_timeseries`) — which call the free Planetary-Computer search directly and accept
no provider argument — so a paid provider has **no route into `consensus.py` by construction**, not because the
sources are inherently free. The shared band math is reused through an internal helper that neither layer's
free/paid status depends on. Keep it that way.

---

## §4 — Billing / credits: two money-flows that must never touch

BUILD_PLAN §4 #3 (two-track capital) and #5 (regulatory shielding) draw a line this section must respect: keep
the **premium-imagery charge** and the **relief-pool disbursement** completely separate.

| Money flow | What it is | Rail | Vehicle |
|---|---|---|---|
| **Premium imagery** (this doc) | user pays Tierva for a parcel close-up / SAR look | SaaS charge → vendor cost pass-through | **DE PBC** (commercial side) |
| **Relief pool** (Pacto) | donor funds an earmarked pool; consensus auto-releases the gift | licensed local payer / mobile-money | the giving rail (BUILD_PLAN §4 #5) |

**Hard rule:** relief-pool funds **never** pay for tasking, and premium billing **never** rides the disbursement
rails. A donor pool buying an ICEYE scene = pool money spent off-mission *and* a commercial scene contaminating
the giving rail. Excluded by design.

**Credits / pre-authorization is the model** (the only safe shape for async, per-km² spend on a self-serve API):

- The user/account holds **pre-purchased credits** (e.g. $X = N km² of Satellogic archive at the §1C rate). The
  resolver's `quote()` (§1B) returns a `Price`; `authorize()` debits credits **before** `order()` spends — so a
  self-serve API can never run an unbounded bill.
- **Pass-through pricing:** charge `vendor $/km² × area × margin` (margin TBD, commercial side). Carry the §1C
  numbers as cost basis: Satellogic ~$4.50/km² archive, ~$12/km² tasking; Umbra $675–4,750/scene; Planet AUM
  ~€665/500 ha/yr; Maxar ~$15–60/km².
- **Tier mapping (RESEARCH §1C → VISION §4 L1/L2/L3):**
  - **L1 SEE** = the **free spine only**. $0 data cost. Never silently bills.
  - **Parcel close-up** = **premium** — a one-off credit spend, *or* bundled into the **L3 Gardener** subscription
    (the "look at MY exact land" promise is L3's, and it's where sub-meter pays for itself).
  - **SAR / event look** = **event-driven** credit spend (or a relief-org/donor account feature), diagnostic-only
    per §3.

---

## §5 — Vendor integration ORDER (cheapest self-serve sub-meter first, rapid SAR second)

Order chosen to (a) ship the cheapest self-serve sub-meter first and (b) reuse the existing source math with the
least new code. API specifics carried from RESEARCH §1C — **confirm against the real API when an account exists**
(§6).

### Vendor #1 — Satellogic (sub-meter optical archive; the resolution upsell)

- **Why first:** **cheapest sub-meter** (~$4.50/km² archive, ~$12/km² tasking) **and self-serve API** — the only
  premium vendor that fits a credits/pass-through model without a sales call.
- **What it unblocks:** resolution gate (§2 case 1) — the parcel close-up the free 10 m spine can't render.
- **Adapter:** `ingest/access/satellogic.py` implementing `ImageryProvider`. Best case (the load-bearing
  assumption, §6): Satellogic exposes a STAC-like archive whose optical assets are signable into the existing
  `odc.stac.load(...)` path → the shared `_ndvi_from_items` math (§1A) runs on the sub-meter pixels via
  `ndvi_render` with the same red/NIR bands. **One known divergence:** `ndvi_timeseries` cloud-masks via the
  Sentinel-2-specific `SCL` band, which Satellogic won't carry (§6 #1/#3) — so the render path needs a
  provider-appropriate cloud mask (the vendor's own QA band, or skip masking for an already-clear tasked scene),
  not a verbatim copy of the SCL step. `quote` = `area_km2 × 4.50`; `order` = immediate for archive, async for
  tasking; `fetch` = signed COG hrefs.
- **Fallback if not STAC:** if the API returns a plain delivery URL (not a STAC item), the adapter writes a thin
  fetch that downloads the COG and hands a local href to the same math — the source loaders read an href either
  way. The integration cost is the search/fetch front, not the math.

### Vendor #2 — Rapid-tasking SAR: ICEYE / Capella (with Umbra as priced fallback)

- **Why second:** delivers the finer/faster all-weather look (§2 case 3) that free Sentinel-1 can't, but it's
  **quote-based** (ICEYE/Capella) — no self-serve credit flow — so it integrates after the self-serve path. Umbra
  has **open pricing** ($675–4,750/scene) so it's the priced fallback for a deterministic credit debit.
- **What it unblocks:** event gate — a same-day, sub-meter flood/storm read when free C-band's 10–20 m / ~6-day
  revisit isn't enough. **Diagnostic/donor-facing only (§3 RED LINE — never a contract input).**
- **Adapter:** `ingest/access/sar_paid.py` implementing `ImageryProvider`, with `mode="rapid-tasking"` and a real
  `eta_hours`. If the delivered product is GRD-like (vv/vh amplitude), `sentinel1_sar.sar_timeseries`'s
  WarpedVRT-from-GCPs read path applies — reuse it. `quote`: Umbra = per-scene table; ICEYE/Capella =
  `status="quote-required"` so the resolver `Blocked`s rather than guesses a price.

### Deferred (not in the first two): Planet, Maxar

- **Planet** (PlanetScope 3 m daily; SkySat sub-meter, archive min $5k; AUM ~€665/500 ha/yr) — strong for the
  **revisit** gate but the AUM/area-subscription model doesn't fit per-km² credits; revisit it for a managed-area
  / enterprise tier.
- **Maxar** (30 cm, ~$15–60/km² via resellers) — finest optical but reseller-gated, not self-serve. A premium
  step **above** Satellogic when 30 cm is specifically required.

---

## §6 — Honesty (the house voice: "NOT yet validated against live data")

This doc is **design-only.** No vendor account exists; no paid pull has run; no real money has moved. Every price
is from RESEARCH §1C (web-verified 2026-06-04), **not a real quote.** Mirroring every loader docstring's
"NOT yet validated against live data," the load-bearing assumptions to **confirm when an account exists** (do NOT
re-verify now — design-only):

1. **(top)** *Satellogic exposes a STAC-like archive whose optical assets are signable into the existing
   `odc.stac` path.* If true, `ndvi_timeseries` runs on paid pixels unchanged. If the real API needs a different
   fetch adapter (auth scheme, delivery-URL instead of STAC item, async-only archive), the §5 fallback applies —
   the math still holds; only the search/fetch front changes.
2. **Per-km² pricing and tasking ETAs are list figures, not contracted.** Real `quote()` values, scene minimums,
   and tasking latency must come from the live account before any credit/margin math is trusted.
3. **Band availability** — that the paid optical product carries the red/NIR (and SAR vv/vh) bands the existing
   source math consumes. Likely but unconfirmed per vendor.
4. **ICEYE/Capella rapid-tasking latency** — whether "same-day" is actually achievable for an arbitrary AOI is
   quote/region-dependent; the resolver's `Blocked`-on-too-slow path (§2) is the honest default until measured.

Nothing in this doc weakens the kernel's auditability claim: the **on-chain trigger remains 100% on the free,
recomputable spine** (§3). Paid imagery is strictly the consumer/diagnostic upsell where the free 10 m spine
honestly fails.

---

*Companion to [VISION.md](VISION.md) (the L1/L2/L3 product), [BUILD_PLAN.md](BUILD_PLAN.md) (the phased build +
two-track / regulatory constraints), and [RESEARCH.md](RESEARCH.md) §1 (the web-verified free+paid data matrix).
Builds on the free access layer in `ingest/access/` and the source contract in `ingest/sources/` — does not fork
either.*
