# Tierva — The Vision

*The full articulation. Consolidates the kernel thesis (from `strategy/GLOBAL_IDEA_AND_RAISE.private.md`,
2026-05-30) with the consumer-platform reframe (2026-06-04) and the web-verified building blocks in
[RESEARCH.md](RESEARCH.md).*

> **Names, layered:** **Tierva** *(tierra + ver — "see your land")* = the platform/product. **Pacto** = the
> giving/auto-pay protocol underneath it. **Pacto Seco** = the drought vertical / proof-of-kernel (live on-chain).

---

## 1. Two faces of one idea

Tierva is one idea you can describe two ways, depending on who's listening.

**To a person:** *"An app that shows anyone, anywhere, the truth about their land — tells them what to grow and
why, future-proofed for the next 20 years — and lets the world fund the farmers who need it."*

**To an investor/funder:** *"A domain-agnostic coordination kernel — open sensing → multi-source consensus →
self-executing code → re-verifiable outcome — that deletes the bureaucratic gap between knowing and acting.
First deployment: drought relief in Latin America."*

These are not in tension. The consumer platform is the **front door** (mass adoption, the human story); the
kernel is the **engine** (the autonomous, verifiable execution); the **giving layer is the bridge** between
them. The discipline (Section 6) is to lead with the wedge and let the kernel be the upside.

## 2. The kernel (the real thesis)

Strip "drought," "land," and "cash" out and what remains is a primitive for **governing any shared resource or
public decision by code that reads the world directly:**

> **Reality → open, universal, recomputable sensing → multi-source consensus (no trusted party) → self-executing code → an outcome anyone can re-verify.**

It is the **missing execution layer** between *"we can now sense the whole planet for free"* and *"systems still
wait on committees to move."* Scaled to its ceiling: relief, allocation, infrastructure, logistics, energy — all
responding autonomously and *verifiably* to real conditions. **No single point of failure. Replicable anywhere.
Owned by no one. Auditable by everyone.**

This is *not* shrunk to fintech. Parametric public finance is **rung one** — the fundable framing, not the idea.

## 3. The proven kernel — what Pacto Seco validated

The hackathon didn't build a drought app. On the hardest possible test case — public money, real lives, real
2023 data, adversarial scrutiny — Pacto Seco validated **every layer of the kernel end-to-end:**

| Kernel layer | Proven by Pacto Seco | Principle |
|---|---|---|
| **Sensing** — free, universal, recomputable | Copernicus consensus index, no auth, no vendor | one substrate; inputs available everywhere |
| **Consensus / integrity** — no trusted party | ≥2 independent sensors must agree; killed the January false-fire | no single point of failure, by design |
| **Autonomous execution** — no human in loop | contract disburses itself when consensus holds 20 days | delete the inherited bureaucratic step |
| **Audit / legitimacy** — trust without a trustee | every input recomputable from public IDs; no commercial oracle | falsifiable by anyone |
| **Replicable archetype** — not a one-off | same engine → any trigger / region / payout | the substrate composes |

**Before:** "wouldn't it be powerful if public systems executed themselves on open data." **After:** a working,
adversarially-verified instance — *the contract is live and clickable on a public chain today.* That is the
difference between a manifesto and a beachhead.

## 4. The consumer platform — See → Understand → Decide

The kernel is the engine. The **product people touch** is a map. You open it, find where you live, and the
satellites tell you about your land. Three tiers, split by the **job done**, not by data inputs:

### L1 — SEE  *(cheap / free → mass adoption)*
*"Show me the truth about my land, now."* Raw satellite intelligence made human-readable per map pin: soil
moisture, crop greenness, rainfall, temperature, terrain, water use. No AI, no jargon. **This is mostly built**
— the 15 loaders + map + multi-sensor panel already do it; the work is packaging and going global.

### L2 — UNDERSTAND  *(affordable upgrade)*
*"What does it mean, and what's coming this season?"* An AI layer **interprets** the data, adds **historical
context** (the 40-year Landsat archive), and a **near-term/seasonal forecast** ("soil drying, rain unlikely 3
weeks, 2 droughts in your last 5 years"). Diagnostic and forward-looking *for the current season* — but it does
**not** prescribe crops. That's the line: L2 explains; L3 decides.

### L3 — THE GARDENER  *(premium → funds everything)*
*"What's the best thing to grow on my exact land — and why?"* The master-agronomist-in-your-pocket. It matches
your location's sun, soil, water, terrain, and climate zone against what crops *thrive* there → a ranked
recommendation **with the reasoning** *("strawberries: ✓ sun ✓ drainage ✓ your rainfall; avoid maíz — too dry by
July")*. The **20-year climate simulation is the secret sauce layered on top** — it future-proofs the pick
*("...and still viable in 2045," or "switch to sorghum in year 12")*. Crucially, the simulation is **bundled with
the prescription** — a "your land is doomed" forecast with no "so do this" is anxiety, not value.

> **Engineering note (from research):** L3 is mostly *wrapping free data, not building climate models.* FAO **GAEZ
> v5** already outputs per-pixel crop suitability (70+ crops) for now *and* 2040/2060/2080/2100 under CMIP6 — free.
> The moat isn't the climate science (FAO did it); it's **fusing** GAEZ (~1 km) + NEX-GDDP trajectory + 10 m
> satellite embeddings + your land's real history into one downscaled, plain-language, per-farm answer no expert
> portal delivers. See [RESEARCH.md](RESEARCH.md) §2–3.

### The giving / auto-relief layer (rides on all three)
L1 users **discover** farmers in need and see the live satellite data justifying it. Donors fund a pool
earmarked to a farmer/region. When Pacto's satellite consensus confirms drought, the contract **auto-releases**
the gift to the farmer's mobile money. Framed as **anticipatory cash transfer / forecast-based financing**
(WFP/IFRC lane) — *not* insurance (which needs a license/underwriter). Radical transparency: **the donor watches
the exact data that fires the payout** — something no charity offers. See [RESEARCH.md](RESEARCH.md) §6.

## 5. The verticals — one engine, many shocks

Pacto Seco (drought) is **vertical #1 / proof-of-kernel**, not the product. The same consensus-and-execute engine
extends cleanly with different sensors and payouts:

- **Pacto Seco** — drought (NDVI + rainfall consensus) · *live*
- **Pacto + flood** — SAR inundation (Sentinel-1 / ICEYE) → relief
- **Pacto + frost / heat** — temperature thresholds → crop protection
- **Pacto + price-collapse** — market feeds → income floor
- …and beyond agriculture: any parametric public decision that today waits on a committee.

## 6. The discipline — vision expansive, ask narrow

The vision is the kernel at civilization scale. **The ask is always a wedge:** the consumer L1/L2/L3 app as the
adoption engine, LAC drought + the IDB pilot as the first real deployment. Funders back a wedge with a credible
first deployment; the global category is the *upside*, not the pitch. Conflating the two is what kills raises.
Full raise mechanics (two-track capital, instruments, funder list, regulatory shielding) live in `strategy/`.

## 7. Open decisions

1. **The fork:** B2C-accessibility-first (the map for everyone) vs. B2G/dev-finance-first (sell the kernel to the
   IDB/governments). Recommended: **B2C front door with the kernel as the engine** — but this is a real strategic
   choice that shapes go-to-market. *(See README — your 2026-06-04 instinct leans B2C; the strategy docs were B2G.)*
2. **The name** — ✅ DECIDED 2026-06-04: platform = **Tierva**, protocol = **Pacto**, drought vertical = **Pacto
   Seco**. (Trademark + domain clearance still TODO before any spend.)
3. **Premium-data business model** — what's free (the global spine), what's paid (parcel close-ups, all-weather
   SAR), who pays. See [RESEARCH.md](RESEARCH.md) §1.
