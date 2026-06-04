# Equity & Dilution — the model (PRIVATE)

*Compiled 2026-06-04. Companion to `GLOBAL_IDEA_AND_RAISE.private.md` + `INVESTOR_2048_VENTURES.private.md`.
Decision on record: **Alex is selling equity** to raise. Floor need: **$600K**. This doc models what that costs
in ownership at each proof stage, so the raise is priced — not guessed.*

---

## The one principle

You are selling equity — good, that's what a SAFE/seed round is. The thing that matters is **not the dollar
amount, it's the VALUATION you sell at.** Same check, different valuation = wildly different ownership given up.

> **Ownership sold = amount raised ÷ post-money valuation.**

And the lever that *raises* the valuation is your **proof gate**: live contract → one real disbursement → IDB
pilot signed. Each milestone bumps the price, so **sequencing is dilution.** Raise the cheap-but-free stuff
(grants) first, sell equity *after* proof, sell *less* of the company for the same money.

## The dilution table — % of the company you give up

*(Post-money SAFE math. Valuations are ILLUSTRATIVE/indicative for a deep-tech pre-seed with a live prototype —
real pre-seed valuations vary widely; treat as a planning frame, not a quote.)*

| Raise ↓ \ Post-money valuation → | **$4M** (now, pre-proof) | **$6M** | **$8M** (post-proof) | **$10M** | **$12M** (strong proof) |
|---|---|---|---|---|---|
| **$600K** (your floor) | 15.0% | 10.0% | 7.5% | 6.0% | 5.0% |
| **$1M** | 25.0% | 16.7% | 12.5% | 10.0% | 8.3% |
| **$2M** | **50.0%** 💀 | 33.3% | 25.0% | **20.0%** ✅ | 16.7% |

**Read the corners:**
- **$2M raised *now* at a $4M pre-proof valuation = you hand over HALF the company.** This is the trap. Don't.
- **$2M raised *after proof* at $10M = 20%** — healthy, standard, the same $2M for *2.5× less* of your company.
- **$600K (your floor) is cheap to hit** — even at a modest $6M valuation it's only **10%**, and grants can cover
  much of it for **0%** (see below).

## What 2048 Ventures' target implies

2048 targets **~15–20% ownership** and leads **$500K–$3M**. Back-solve the valuation they'd need:

| If 2048 puts in… | …for 15% | …for 20% |
|---|---|---|
| $600K | $4.0M post | $3.0M post |
| $2M | $13.3M post | $10.0M post |

→ For 2048 to write a **$2M** lead at a healthy 15–20%, you need a **~$10–13M post-money** — which only the
**proof unlock** supports. Pre-proof, a $2M 2048 check would cost you 30–50%. So with 2048 specifically: **either
take a smaller Fast-Track check now ($250–750K, fits your $600K floor) OR wait for proof to take the $2M without
over-diluting.** Both are fine; the middle (big check, no proof) is the one to avoid.

## The recommended sequence (hit the floor cheaply, sell equity at a good price)

1. **NOW — grants to the $600K floor (0% dilution).** Stellar / Gitcoin / Celo / Mercy Corps / IDB Lab (see
   `FUNDRAISING_STRATEGY.private.md`). Grants cost **no equity** and *raise your proof* → they make the later
   equity *more* expensive for investors (better for you). Grants are **not** a priced round, so they keep you
   **2048 Fast-Track-eligible** (their cutoff is >$2M already raised).
2. **OPEN 2048 now, sell at the unlock.** First contact pre-proof (their lane); the **term-sheet ask fires at the
   proof unlock**, when the valuation supports a $1–2M lead at 15–20%.
3. **Result:** floor covered for ~free, real runway raised at a healthy price, you keep **~80%+** through seed.

## Cap-table hygiene (do these before you sell a share)

- **Settle the Alex ⇄ JC founder split FIRST.** Co-founder equity comes out of the *founder* pool (before
  investors), and 2048's #1 criterion (founder-market-fit) needs JC as a *titled co-founder*. Decide the split
  while the cap table is clean — retrofitting it after a raise is painful. *(Gated on JC's answer to the
  2026-06-04 vision message.)*
- **Sell into the Delaware C-corp**, not the NM LLC. The C-corp is the equity vehicle (QSBS-eligible, what 2048
  expects). The NM LLC (infra/assets) is debt/asset-financed separately — keep it **out** of the equity round so
  hardware CapEx never dilutes the operating company.
- **Use a standard post-money SAFE** (YC template). Post-money = the investor's % is locked at signing (no
  surprise dilution from later SAFEs landing in the same round) — cleaner for you to reason about.
- **Track CUMULATIVE dilution.** Two 20% rounds ≠ 40% kept — it's 0.8 × 0.8 = **64% kept**. Each round compounds;
  keep founder ownership healthy across the whole sequence, not just one round.

## Honest caveats

- Valuations above are a **planning frame**, not promises — pre-seed pricing is negotiated and varies by market,
  team, and proof. Anchor every number to the proof you actually have at the time.
- Selling equity is correct here; the discipline is **price + sequence**, not avoidance.
- This models the **operating-company (Track A) equity** only. Infra (Track B, NM LLC) is financed against the
  asset, separately — see `GLOBAL_IDEA_AND_RAISE.private.md` §7.
