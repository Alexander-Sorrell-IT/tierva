# Tierva

***Ve tu tierra — see your land.***

**See your land the way the satellites do — learn what to grow on it — and let the world protect the farmers who feed it.**

Tierva *(tierra + ver — "see your land")* is a consumer Earth-intelligence platform: a dead-simple map where
**anyone — no degree, no jargon — finds where they live and learns what the satellites know about it**
(moisture, crops, weather, rainfall, temperature, terrain). On top sits an AI advisor that tells you **what to
grow and why**, future-proofed against how your land will change over the next 20 years. And underneath runs
**Pacto** — a giving / auto-pay protocol: people fund poor farmers anywhere, and a self-executing contract pays
them the moment satellites confirm a drought.

It's a weather app and a radar app, fused — and then surpassed by turning *seeing* into *deciding* and *giving*.

> **Names, layered (no clash):** **Tierva** = the platform/product. **Pacto** = the giving/auto-pay protocol
> underneath it. **Pacto Seco** = the drought vertical / proof-of-kernel (live on-chain today).

---

## The three tiers — See → Understand → Decide

| Tier | The job | What you get | Cost |
|---|---|---|---|
| **L1 — SEE** | *"Show me the truth about my land."* | Raw satellite intelligence made human-readable: moisture, crops, rain, temp, terrain — **now**. No AI. | Cheap / free |
| **L2 — UNDERSTAND** | *"What does it mean, and what's coming this season?"* | AI **interprets** the data + **history** + **near-term forecast**. Diagnostic, actionable now. | Affordable |
| **L3 — THE GARDENER** | *"What should I grow here, and why?"* | The master-agronomist-in-your-pocket: ranks the best crops for **your exact spot** with the reasoning *("plant strawberries — your sun, soil, water match")*, **future-proofed** by a 20-year climate simulation. | Premium |

The **giving / auto-relief layer (Pacto) rides on all three**: L1 users discover farmers in need and see the
live satellite data; donors fund a pool; when the satellite consensus confirms drought, the contract pays the
farmer automatically. Radical transparency no charity offers — *you watch the data that fires the payout.*

## Why this can win (the moats — web-verified, see [docs/RESEARCH.md](docs/RESEARCH.md))

1. **The un-degreed consumer slot is unclaimed.** Every *free, powerful* EO tool (Copernicus Browser, Digital
   Earth Africa, Google Earth Engine) demands EO/Python literacy; every *easy* tool (OneSoil, Climate FieldView)
   assumes you already farm a managed field and know what NDVI means. **Nobody serves the person who just wants
   to point at their home and be told, plainly, what the sky sees.** That's L1.
2. **Nobody ships 20-year, per-individual crop suitability.** FAO's GAEZ v5 already computes it globally for free
   — but only as expert GeoTIFFs with no consumer UX. The moat is *fusing* it with satellite history + 10 m
   embeddings into one personalized, plain-language answer. That's L3 / "the gardener."
3. **The giving + satellite + auto-relief fusion doesn't exist.** Parametric insurers (Pula, OKO, ACRE) have the
   trigger but sell B2B with no donor layer; GiveDirectly/Kiva have donors but no satellite trigger. Pacto (the
   protocol under Tierva) fuses all three.

## The kernel underneath (the real thesis)

Strip "land" and "crops" away and what remains is a **domain-agnostic coordination kernel**:

> **Reality → open, recomputable sensing → multi-source consensus (no trusted party) → self-executing code → an outcome anyone can re-verify.**

It deletes the human bureaucratic bottleneck between *knowing* and *acting*. Tierva (the consumer app) is the
**front door**; the Pacto kernel (proven by Pacto Seco) is the **engine**; giving is the **bridge**. Full thesis
in [docs/VISION.md](docs/VISION.md).

## Status — proven at the smallest rung

- **Pacto Seco** (drought, Honduras Dry Corridor) is the **proof-of-kernel / first vertical, not the product.**
  On the hardest test (public money, real lives, real 2023 data, adversarial scrutiny) it validated every kernel
  layer end-to-end, and the smart contract is **live and clickable on a public chain** today.
- **Already built (the L1 spine):** 15 real satellite/sensor loaders (Copernicus/NASA/MODIS…), a map UI, a
  multi-sensor panel, a deployed consensus contract. *L1 is closer to built than it looks.*
- **Net-new:** go global, the L2 AI advisor, the L3 GAEZ-powered gardener, the giving UX, premium-data adapters.
- Code repo of the drought vertical: `Alexander-Sorrell-IT/pacto-seco`. **This repo (`tierva`) = the platform
  vision + strategy + build plan.**

## Honesty rule (load-bearing, everywhere)

The kernel is *proven at the smallest rung* — one municipality, real data, a public **testnet**. Civilization
scale is the **trajectory that rung opens, not a claim that it's built.** Every dollar figure is stage-gated.
We never sell what isn't running. (This candor is an asset in diligence, not a liability.)

## Repo map

- [`docs/VISION.md`](docs/VISION.md) — the full vision: kernel, the Tierva consumer platform, the 3 tiers, how the verticals extend.
- [`docs/RESEARCH.md`](docs/RESEARCH.md) — web-verified building blocks: the free data spine, the GAEZ "gardener" engine, climate-sim, AI, competitors/moats, map-tech & costs, giving rails.
- [`strategy/`](strategy/) — **PRIVATE** raise strategy (two-track capital, funder list, 90-day plan, regulatory). Not for judges/teammates.

## Name notes

**Tierva** = *tierra* (land) + *ver* (to see) → "see your land"; reads as land/earth to English ears, native-warm
in Spanish (first market: LatAm). Chosen 2026-06-04 over a 35-name field (web-checked cleanest/most ownable; the
real-word bilingual options — Savia, Veo, Verde, Vida — were all trademark-crowded). **Pacto** stays the
giving/relief protocol; **Pacto Seco** the drought vertical. *Formal trademark + domain clearance still TODO
before any spend.*
