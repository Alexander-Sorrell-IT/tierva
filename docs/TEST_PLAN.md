# Tierva — TEST PLAN (executable)

> Alex asked "how do we test this, what is the next step" **first**. This doc answers
> both with commands you can paste, concrete AOIs, and a binary definition of "pass"
> for every rung. It builds on the state in `RESEARCH.md` / `VISION.md` / `BUILD_PLAN.md`
> — it does not re-derive them. Where a thing is already green, the command that
> proves it is here so it stays reproducible.

Paths are absolute. The Python interpreter everywhere is the Pacto Seco venv (has
pandas/numpy/shapely/odc.stac/rioxarray/rasterio):

```
PY=/Users/broodierchip-m1air/Documents/Hackthon/taikai/projects/copernicuslac-seguridad-alimentaria-2026/pacto-seco/.venv/bin/python
TIERVA=/Users/broodierchip-m1air/Documents/Hackthon/tierva
```

---

## 0. The pyramid at a glance (reality, not aspiration)

| Rung | What it covers | State today | Network | Cost to run |
|------|----------------|-------------|---------|-------------|
| **U** Unit | kernel math + Solidity contract logic | **GREEN** — 16 py + 26 forge | none | seconds |
| **S** Smoke | all 8 loaders **import** cleanly | **MISSING** (write first; trivial) | none | seconds |
| **L** Live-loader | each loader actually **pulls** real data | **1/8 proven** (Sentinel-2 only) | yes | minutes |
| **I** Integration | live loader → climatology → consensus on a fresh AOI | **NOT DONE** (the prize rung) | yes | minutes |
| **E** On-chain e2e | anvil deploy → oracle push → fire → claim | **GREEN** (Concepción 2023, cached) | local | ~1 min |
| **P** Perf | per-scene read throughput | **finding logged, no fix** (~4 s/scene) | yes | minutes |
| **R** Regression/CI | run U+S on every change; L/I gated | **NONE** (recommend) | mixed | seconds |

The gap is the **right-hand column going down**: unit is solid, on-chain e2e is
solid, but the *data spine has only been exercised on one of eight loaders*, and
the loaders have **never been wired through the kernel on a parcel we did not
already cache**. Everything below is ordered to close that, cheapest rung first.

---

## U — Unit (EXISTS, GREEN — keep it that way)

### U1. Kernel (consensus + climatology)

```
$PY $TIERVA/tests/test_consensus.py
```

Pass = `ALL PASS (16 tests)`, exit 0. These mirror `Pacto.sol` case-for-case
(`tests/test_consensus.py` routes single-signal cases through
`apply_consensus_trigger(sensors=["signal"], min_sensors=1)` so the run/gap/
confirmations logic is the same code path the contract enforces). The
load-bearing ones to never let regress:

- `test_two_readings_gap_21_no_fire` — span looks like 20 but the 21-day gap
  restarts the run. A span-only impl wrongly fires; catches a missing gap-restart.
- `test_confirmations_clause_is_load_bearing` — the only pair where
  `min_confirmations` alone flips the decision (`persistence_days=20, max_gap=30`).
- `test_direction_above_fires` / `..._below_values_no_fire` — proves the kernel is
  direction-agnostic (heat/flood, not just drought).
- `test_zscore_anomaly_math`, `test_climatology_nan_std_single_obs` — the anomaly
  math + the single-obs → NaN-std guard.

### U2. Contract (`Pacto.sol`)

```
cd $TIERVA/contracts && forge test
```

Pass = `26 passed; 0 failed`. The discriminating on-chain tests (`Pacto.t.sol`):

- `test_consensus_singleSensor_reverts` — a scene where only 1 sensor breaches
  **reverts on-chain** ("consensus not met"); the 2-sensor rule is in Solidity, not
  in an off-chain script the oracle could fake.
- `test_irregularCadenceStillFires` — weekly Sentinel cadence (days 100/107/114/121)
  fires; this is the cadence bug the kernel mirrors.
- `test_noDisburse_severeReadings21DaysApart` / `..._30DaysApart` — unobserved gaps
  do not pay out.
- `test_cannotReplayOldCycle`, `test_withdrawOnlyFreeNotReserved`,
  `test_blacklistedBeneficiaryDoesNotBrickPool` — replay, escrow-reservation, and
  pool-bricking guards.
- `test_direction_above_firesOver20Days` + the heat-pool consensus pair — the second
  pool config (`breachBelow=false`) proves the comparator respects direction at
  **both** the consensus-count site and the run-advance site.

**Definition of regression-clean:** `U1 == 16/0` and `U2 == 26/0`. Any drop blocks.

---

## S — Smoke (WRITE THIS FIRST — zero network, catches the refactor)

The 8 loaders were transcribed from pacto-seco and re-pointed at the new
`ingest/access/*` shared patterns (`from ..access.planetary_computer import search`,
etc.). A single broken relative import or a renamed symbol fails silently until a
live pull — so gate it with an offline import smoke test.

```
cd $TIERVA && for m in sentinel2 sentinel1_sar worldcover_cropland \
  modis_ndvi modis_lst smap chirps era5_rain; do \
  $PY -c "import importlib; importlib.import_module('ingest.sources.$m'); print('OK  $m')" \
  || echo "FAIL $m"; done
```

Also smoke the access layer and kernel imports:

```
cd $TIERVA && $PY -c "import ingest.access.planetary_computer, ingest.access.earthdata, ingest.access.cds; \
import kernel.consensus, kernel.climatology; print('access+kernel import OK')"
```

Pass = 8× `OK` + the access/kernel line, no `FAIL`, no traceback. Suggested home:
`$TIERVA/tests/test_imports.py` (a bare loop like `test_consensus.py`, no pytest).
This is the fastest possible guard and belongs in CI (no creds, no net).

---

## L — Live-loader validation (THE BIG GAP: 1 of 8 proven)

Reality from `RESEARCH.md §1` resolution truth, restated as a test matrix:

| Loader | Resolution | Parcel-capable? | Auth | Validatable today? |
|--------|-----------|-----------------|------|--------------------|
| `sentinel2.ndvi_timeseries` | 10 m | **YES** | none | **PROVEN today** (mean 0.378, CA) |
| `sentinel1_sar.sar_timeseries` | 10–20 m | **YES** | none | **#1 — not yet run** |
| `worldcover_cropland.cropland_mask` | 10 m | **YES** | none | **#1 — not yet run** |
| `modis_ndvi.modis_ndvi_timeseries` | 250 m | field→region | none | yes (no-auth) |
| `modis_lst.lst_timeseries` | 1 km | region-only | none | yes (no-auth) |
| `chirps.chirps_timeseries` | ~5 km | region-only | none | yes (no-auth) |
| `smap.smap_timeseries` | ~9 km | region-only | **Earthdata bearer** | yes — token at `~/.edl_token`, valid to 2026-07-29 |
| `era5_rain.precip_monthly` | ~9 km | region-only | **CDS key** | **BLOCKED until `~/.cdsapirc` exists** (open Q) |

> Not in scope: GRACE / ET / GOES / cgls / ccism are described in `RESEARCH.md`
> prose/docstrings but are **not files** in `ingest/sources/`. No steps for them.

**Canonical test parcel** (the one Sentinel-2 was proven on — reuse it so SAR,
WorldCover, MODIS all describe the *same* ground):

```
California Central Valley:  lon=-119.70  lat=36.60   (irrigated farmland)
period:                     start="2023-04-01"  end="2023-09-30"   (one CA growing season)
AOI polygon:                ~2 km box around the point (shapely.geometry.box)
```

### L1. Sentinel-2 NDVI — already proven (re-run to confirm parcel pull)

```
$PY - <<'PY'
import sys; sys.path.insert(0, "/Users/.../tierva")  # use $TIERVA
from shapely.geometry import box
from ingest.sources.sentinel2 import ndvi_timeseries
g = box(-119.71, 36.59, -119.69, 36.61)
df = ndvi_timeseries(g, "2023-04-01", "2023-09-30")
print(df.head(), "\nrows:", len(df), "ndvi_mean range:", df.ndvi_mean.min(), df.ndvi_mean.max())
assert len(df) > 0 and df.ndvi_mean.between(-1, 1).all()
print("S2 PASS")
PY
```

Pass = ≥1 scene; every `ndvi_mean ∈ [-1, 1]`; irrigated CA should land roughly
0.2–0.8 in season (Sentinel-2 proven at **0.378** today is in band).

### L2. Sentinel-1 SAR — **immediate next action (#1a)**

This loader's docstring documents a real failure mode: `odc.stac.load` produced
**all-NaN backscatter** because S1-GRD assets are in raw radar geometry (GCP-only,
`crs==None`) and GDAL couldn't apply the GCPs; the fix is the explicit
`WarpedVRT(src, src_crs=gcp_crs, crs="EPSG:4326")` read. **So the pass criterion
*is* the bug check:** `vv_db` must come back **finite, not NaN**.

```
$PY - <<'PY'
import sys, numpy as np; sys.path.insert(0, "/Users/.../tierva")  # $TIERVA
from shapely.geometry import box
from ingest.sources.sentinel1_sar import sar_timeseries
g = box(-119.71, 36.59, -119.69, 36.61)
df = sar_timeseries(g, "2023-04-01", "2023-09-30")
print(df.head(), "\nrows:", len(df))
assert len(df) > 0,                         "no S1 scenes returned"
assert np.isfinite(df.vv_db).any(),         "ALL vv_db NaN — the GCP/WarpedVRT path is broken"
assert df.vv_db.dropna().between(-40, 10).all(), "vv_db out of plausible relative-dB range"
print("S1 PASS — finite vv_db:", df.vv_db.dropna().tolist()[:5])
PY
```

Pass = ≥1 scene; **at least some `vv_db` finite** (this directly exercises the
documented all-NaN regression); finite values within a plausible relative-dB band
(~ -40…+10 dB). On a second run it should read from `data_cache/sar_<hash>.parquet`
(see P/R below) — confirm the parquet appears.

### L3. WorldCover cropland mask — **immediate next action (#1b)**

Pass criterion is **substantive coverage**, not "ran": Central Valley is farmland,
so the class-40 mask must be materially True.

```
$PY - <<'PY'
import sys; sys.path.insert(0, "/Users/.../tierva")  # $TIERVA
from shapely.geometry import box
from ingest.sources.worldcover_cropland import cropland_mask
g = box(-119.71, 36.59, -119.69, 36.61)
m = cropland_mask(g)
frac = float(m.values.mean())
print("mask dims:", dict(m.sizes), "cropland fraction:", frac)
assert m.values.size > 1,        "got the 1x1 no-coverage fallback — no WorldCover for bbox"
assert frac > 0.10,              "Central Valley should be substantially cropland (class 40)"
print("WorldCover PASS — cropland_frac", round(frac, 3))
PY
```

Pass = mask is a real 2-D grid (not the 1×1 no-coverage fallback) AND cropland
fraction > ~0.10 over this irrigated parcel. (Tune the floor after the first run;
the point is "the mask is true where there is farmland," not a magic number.)

### L4. Second-continent parcel (proves global, not CA-only)

Repeat L1–L3 on a parcel on a different continent to prove the loaders are not
silently CA-tuned. Recommended: **Honduras Dry Corridor, Concepción de María**
(the contest AOI; ~ lon -87.18, lat 13.40) — same three assertions. This also
sets up the apples-to-apples check against the **cached** Concepción series the
oracle already uses (a value sanity-cross-check, not byte-equality, since the new
loaders read live at coarser default resolution).

### L5. Region-only loaders (no-auth first, then auth)

No-auth, runnable today on the CA parcel (resolution-honest: these are
region-context, not parcel):

```
# MODIS NDVI (250 m), MODIS LST (1 km), CHIRPS (~5 km) — each: rows>0, values in band
$PY - <<'PY'
import sys; sys.path.insert(0, "/Users/.../tierva")  # $TIERVA
from shapely.geometry import box
g = box(-119.8, 36.5, -119.6, 36.7)   # wider box: these are coarse
from ingest.sources.modis_ndvi import modis_ndvi_timeseries
from ingest.sources.modis_lst import lst_timeseries
from ingest.sources.chirps import chirps_timeseries
for name, fn in [("modis_ndvi", lambda: modis_ndvi_timeseries(g, "2023-04-01", "2023-09-30")),
                 ("modis_lst",  lambda: lst_timeseries(g, "2023-04-01", "2023-09-30")),
                 ("chirps",     lambda: chirps_timeseries(g, "2023-04-01", "2023-09-30"))]:
    df = fn(); print(name, "rows:", len(df)); assert len(df) > 0, name + " empty"
print("REGION no-auth PASS")
PY
```

Auth-gated:
- **SMAP** — token present (`~/.edl_token`, to 2026-07-29). Same pull shape; pass =
  rows > 0 and no `EarthdataAuthError`.
- **ERA5 (`era5_rain.precip_monthly`)** — needs a CDS key in `~/.cdsapirc`.
  `ingest/access/cds.setup_cdsapirc(key)` writes it, **but the key itself is not
  known to be present** → see Open Questions. Do not run this step until the key
  exists; until then ERA5 stays a documented blocker.

---

## I — Integration: live loader → climatology → consensus (the prize rung)

This is the rung that proves the *whole spine* on data we did not pre-cache. A real
**consensus** test needs ≥2 *parcel-resolution* time series; on one parcel those are
exactly **Sentinel-2 NDVI** and **Sentinel-1 SAR**. (WorldCover is a *mask that
refines NDVI*, not a third series.) The stack:

```
S2 NDVI (cropland-masked via WorldCover)  ── zscore_anomaly ──┐
                                                              ├─ merge on date ─ apply_consensus_trigger(min_sensors=2)
S1 SAR vv_db                              ── zscore_anomaly ──┘
```

`apply_consensus_trigger` (default `threshold=-1.2, persistence_days=20,
max_gap_days=14, min_confirmations=3, direction="below"`) decides fire/no-fire — the
**same** predicate the contract enforces.

**"Pass" must be a known outcome, not "it ran."** Pick two CA Central Valley periods
with opposite ground truth (verify the years against the **US Drought Monitor**
before committing them in the doc):

- a **drought year/season** at this parcel → consensus **SHOULD fire**
  (`triggered.any() == True`, `first_trigger_date` inside the dry window);
- a **wet/normal year** → consensus **SHOULD NOT fire** (`triggered.any() == False`).

Skeleton (`$TIERVA/tests/test_integration_live.py`, network-gated):

```
$PY - <<'PY'
import sys, pandas as pd; sys.path.insert(0, "/Users/.../tierva")  # $TIERVA
from shapely.geometry import box
from ingest.sources.sentinel2 import ndvi_timeseries
from ingest.sources.sentinel1_sar import sar_timeseries
from kernel.climatology import zscore_anomaly
from kernel.consensus import apply_consensus_trigger, first_trigger_date

g = box(-119.71, 36.59, -119.69, 36.61)
BASE = [2019, 2020, 2021, 2022]          # climatological normal (pre-target)
# fetch a multi-year window so climatology has a baseline + the target season:
ndvi = ndvi_timeseries(g, "2019-01-01", "2023-12-31")
sar  = sar_timeseries(g,  "2019-01-01", "2023-12-31")
ndvi = zscore_anomaly(ndvi, "ndvi_mean", BASE, out_col="ndvi_anom")
sar  = zscore_anomaly(sar,  "vv_db",     BASE, out_col="sar_anom")
m = pd.merge(ndvi[["date","ndvi_anom"]], sar[["date","sar_anom"]], on="date", how="inner")
out = apply_consensus_trigger(m, sensors=["ndvi_anom","sar_anom"], min_sensors=2)
print("fired:", bool(out.triggered.any()), "first:", first_trigger_date(out))
# DROUGHT-YEAR run -> assert out.triggered.any() is True
# WET-YEAR run     -> assert out.triggered.any() is False
PY
```

Pass = **both** the drought case fires and the wet case does not, with the fire date
landing in the dry window. Notes that make this honest:
- SAR↔soil-moisture weakens under dense canopy and mixes orbit geometry (loader
  docstring) — SAR is a *corroborating* sensor; the NDVI+SAR pair is exactly the
  "two independent sensors must agree" rule, now on **live** data.
- The merge is an inner join on date; S2 (~5-day) and S1 (~6/12-day) cadences won't
  coincide on most days, so expect few co-observed scenes — this is realistic and is
  why `max_gap_days` matters. If too few rows survive the join, resample/forward-fill
  to a common cadence before the merge and note it.
- Second-continent variant: rerun on Concepción (HN) for a season with a **known**
  drought outcome and assert it matches the cached backtest's verdict.

---

## E — On-chain end-to-end (GREEN — Concepción 2023, cached)

Already proven on local anvil (deploy → oracle pushes real 2023 series → Jan blip
rejected on-chain → real drought fires at dayIndex 186 → beneficiary claims real
USDC). Reproduce:

```
# 1. local chain
anvil &                       # http://localhost:8545, prints funded keys
# 2. deploy
cd $TIERVA/contracts && forge script script/DeployPacto.s.sol \
  --rpc-url http://localhost:8545 --broadcast --private-key <ANVIL_KEY_0>
# 3. push the real series + watch it fire
$PY $TIERVA/oracle/oracle.py --rpc http://localhost:8545 \
  --pacto <DEPLOYED_ADDR> --oracle-key <ANVIL_ORACLE_KEY> \
  --pool tierva:concepcion:drought --cycle 2023
```

Pass = oracle reports the Jan single-scene blip **rejected** (no run started), the
sustained drought **fires** mid-year, `disbursed == true`, and a beneficiary
`claim()` moves USDC. `--dry-run` first to print the predicted acceptance table
without sending.

**Known integration seam (the wiring gap, NOT a regression):** today
`oracle.concepcion_2023_series()` builds the on-chain series from the **old
`pacto_seco.*` cache** (`from pacto_seco.municipios... import load_dry_corridor`,
`pacto_seco.data.era5_loader`, `pacto_seco.index.dcsi`) — it does **not** call the
new `ingest/sources/*` loaders. So the new generic data spine has been proven to
*pull* (rung L) and to *decide* (rung I), but has **never fed the contract**. The
fix is a downstream milestone (see Next Steps #4): a Tierva-native series builder
that runs L+I and emits the `(dayIndex, [int anomalies×100])` scene list the oracle
already consumes — replacing the `pacto_seco` dependency. Do this only **after**
L and I are green; you can't wire an unproven loader into the oracle.

---

## P — Performance / benchmark (anchor to the real finding)

**Measured finding (today):** `sentinel2.ndvi_timeseries` reads scenes
**sequentially** in a Python `for t in ndvi.time.values:` loop, calling
`frame.values` per timestep (~**4 s/scene**). Wide date ranges are slow; the
spatial-mean-per-scene loop is the bottleneck. The same pattern recurs in
`sar_timeseries` (per-item `_read_asset_mean_db`).

**Fix-and-measure task (correctness-preserving):**
1. Replace the per-`t` Python loop with one vectorized reduction over the time dim —
   `ndvi.mean(dim=("x","y"))` / `ndvi.where(...).mean(...)` and a single
   `.compute()` (the cube is opened with `chunks={}` → dask-lazy, so this fuses).
2. **Pass = same answer, faster:** the vectorized series must equal the loop series
   within float tolerance (`np.allclose(old.ndvi_mean, new.ndvi_mean, atol=1e-6)`)
   **and** wall-clock materially lower (target ≥3× on a 12-month CA pull). *A faster
   wrong answer fails.*

```
# before/after, same AOI+period, time it and diff the series
$PY - <<'PY'
import time
# t0 = time.time(); old = ndvi_timeseries(...);  t_old = time.time()-t0
# t0 = time.time(); new = ndvi_timeseries_vec(...); t_new = time.time()-t0
# assert np.allclose(old.ndvi_mean, new.ndvi_mean, atol=1e-6)
# print("speedup", round(t_old/t_new, 1), "x")
PY
```

Secondary perf lever: the SAR loader already caches to `data_cache/`; ensure S2 and
the region loaders cache the same way so repeat pulls are O(read-parquet).

---

## R — Regression / CI (NONE today — recommend)

No CI exists. Minimum viable pipeline, split by network dependency:

**Every commit / PR (offline, fast, hard-gate):**
```
$PY $TIERVA/tests/test_consensus.py          # U1  -> ALL PASS (16)
cd $TIERVA/contracts && forge test           # U2  -> 26 passed; 0 failed
$PY $TIERVA/tests/test_imports.py            # S   -> 8 loaders import (write this)
```
These need no network or credentials and must be green to merge.

**Network-gated job (nightly or `[live]` label), never on the hot path:**
- L (live pulls) + I (live integration) behind an env flag, e.g.
  `TIERVA_LIVE=1 $PY tests/test_integration_live.py`; default-skip when unset.
- **Fixtures are already in the repo design:** `sar_timeseries` caches to
  `data_cache/sar_<hash>.parquet` keyed on (bounds, dates, resolution). Those cache
  files **are** the network-free replay fixtures — commit a small set and CI replays
  them with zero network; only the flagged live job actually hits Planetary Computer /
  Earthdata. Give S2 and the region loaders the same cache-to-parquet behavior so the
  whole spine is CI-replayable.

Suggested layout: a GitHub Actions matrix with an `offline` job (always) and a
`live` job (`if: contains(labels, 'live')` or schedule), the live job consuming
`~/.edl_token` / `~/.cdsapirc` from secrets.

---

## NEXT STEPS — prioritized, executable

1. **Validate the remaining parcel-capable loaders on the SAME California parcel.**
   Run **L2 (Sentinel-1 SAR)** and **L3 (WorldCover)** at lon=-119.70, lat=36.60,
   2023-04-01…09-30.
   *Pass:* SAR returns ≥1 scene with **finite `vv_db`** (kills the documented
   all-NaN GCP regression); WorldCover returns a real 2-D mask with cropland
   fraction > ~0.10. This is the cheapest highest-value empirical move and is
   blocked by nothing (no auth).

2. **Prove global, not CA-only:** rerun L1–L3 on a **second-continent** parcel —
   Concepción de María, Honduras (~ -87.18, 13.40). Same three assertions.
   *Pass:* same shape of result; SAR finite, WorldCover cropland present.

3. **Full live integration test (rung I):** feed live S2-NDVI (cropland-masked) +
   S1-SAR through `zscore_anomaly` → `apply_consensus_trigger(min_sensors=2)` on a
   **known-outcome** CA drought season vs a wet season (years verified against the
   US Drought Monitor). *Pass:* drought season fires, wet season does not, fire date
   inside the dry window. This is the first end-to-end proof of the generic spine on
   uncached data.

4. **Wire the proven loaders into the oracle (close the E-rung seam):** write a
   Tierva-native series builder that runs steps 1–3 and emits the
   `(dayIndex, [anomaly×100])` scene list `oracle.py` already consumes, replacing the
   `pacto_seco.*` cache dependency in `concepcion_2023_series`. Re-run rung E on
   anvil end-to-end. *Pass:* contract fires from a series produced **entirely** by
   `ingest/sources/*` + `kernel/*`, no `pacto_seco` import.

5. **Perf fix (rung P):** vectorize the per-scene spatial-mean loop in
   `sentinel2.ndvi_timeseries` (then SAR). *Pass:* vectorized == loop within
   `atol=1e-6` AND ≥3× faster on a 12-month pull.

6. **Stand up CI (rung R):** offline job (U1+U2+S) on every commit; network-gated
   job (L+I) nightly/labeled, replaying `data_cache/*.parquet` fixtures with live
   pulls behind `TIERVA_LIVE=1`. Add the import smoke test `tests/test_imports.py`
   as part of this.

7. **Backfill region loaders (rung L5):** smoke-pull MODIS-NDVI / MODIS-LST / CHIRPS
   (no-auth, today) and SMAP (token present). Defer ERA5 until the CDS key exists.

---

## OPEN QUESTIONS / BLOCKERS

- **CDS key for ERA5.** `era5_rain.precip_monthly` needs `~/.cdsapirc`
  (`ingest/access/cds.setup_cdsapirc(key)` writes it from a personal access token).
  Is a CDS token available (e.g. in `~/Desktop/rhis/hunt-keys.env`)? Until then ERA5
  is the one loader that **cannot** be live-validated; SAR fills the second-sensor
  slot for parcel consensus, so this does not block rung I.
- **Known-outcome CA years for rung I.** Which specific Central Valley
  drought-season and wet-season years should anchor the SHOULD-fire / SHOULD-NOT-fire
  integration assertions? Pick from the US Drought Monitor record and pin them so the
  test is deterministic.
- **WorldCover cropland-fraction floor.** The >0.10 threshold in L3 is a first guess;
  set the real floor after the first live pull at this parcel.
- **S2↔S1 cadence join.** Inner-joining ~5-day S2 with ~6/12-day S1 yields few
  co-observed dates; decide resample/forward-fill strategy for the integration merge
  and record it (affects `max_gap_days` realism).
