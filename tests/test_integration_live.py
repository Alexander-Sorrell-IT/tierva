"""Integration-tier (NETWORK) test: live loader -> kernel climatology -> kernel
consensus, end to end on REAL Earth-observation data.

This is the PRIZE wiring proof: it shows the same parametric pipeline that backs
the on-chain trigger runs on real satellite bytes, fires on a real drought, and
does NOT fire on a real green/normal year.

Run (Pacto Seco venv has pandas/numpy/rasterio/odc.stac/planetary_computer):
  RUN_NETWORK_TESTS=1 \
    /Users/broodierchip-m1air/Documents/Hackthon/taikai/projects/\
copernicuslac-seguridad-alimentaria-2026/pacto-seco/.venv/bin/python \
    /Users/broodierchip-m1air/Documents/Hackthon/tierva/tests/test_integration_live.py

NETWORK GATE (so CI can gate it)
================================
This file hits Microsoft Planetary Computer over the network for the live
Sentinel-2 pull. CI must opt in:
  * It is SKIPPED (exit 0, "SKIPPED (network gate)") unless the environment
    variable RUN_NETWORK_TESTS=1 is set.
  * If the live pull raises a transport/IO error at runtime (offline runner,
    PC outage), the live test is reported SKIPPED, not FAILED — a network
    outage is not a logic regression. The OFFLINE cached-data assertions still
    run and still gate.

WHAT IS LIVE vs WHAT IS CACHED (reported honestly)
==================================================
1) LIVE loader -> kernel (real bytes, this run, over the network):
   ingest.sources.sentinel2.ndvi_timeseries on the California Central Valley
   parcel box(-119.7025, 36.5975, -119.6975, 36.6025), July 2023, cloud<20.
   Returns a handful of real NDVI scenes (~0.39-0.42). We push them through
   zscore_anomaly -> composite_signal -> apply_consensus_trigger to prove the
   full loader->climatology->consensus path executes on freshly-downloaded
   satellite data and yields a finite NDVI series + a complete trigger frame.
   (A single calendar month cannot form a multi-year climatology, so this live
   leg's anomaly is only a within-month z-score, NOT a meaningful multi-year
   drought anomaly; its job is to prove the LIVE loader->kernel wiring on real
   bytes, not to decide a payout.)

2) CACHED multi-year drought decision (the fire / no-fire assertions):
   The fire/no-fire decision needs a multi-year monthly climatology (a baseline
   + a target year). A fresh multi-year live pull is slow (~minutes), so per the
   task's explicit sanction we reuse the Pacto Seco data_cache Sentinel-2 NDVI
   for the known Honduras 2023 drought (Concepcion de Maria). These parquets are
   themselves the output of the SAME ndvi_timeseries loader, persisted earlier.
   Same kernel, same params (contract defaults), SAME baseline (2019-2022) for
   both poles:
       * target 2023 (the drought year)  -> FIRES
       * target 2021 (the greenest year) -> does NOT fire
   Identical baseline + identical kernel + only the target year changes => the
   cleanest possible "drought fires, green year doesn't" demonstration.

KERNEL UNDER TEST
=================
  kernel.climatology.zscore_anomaly        (the z-score anomaly fn)
  kernel.consensus.composite_signal        (the named composite, exercised)
  kernel.consensus.apply_consensus_trigger (contract-fidelity trigger)
Defaults mirror PactoSeco.sol: threshold -1.2, persistence 20d, max_gap 14d,
min_confirmations 3. A single-sensor NDVI-only consensus
(sensors=["signal"], min_sensors=1) is used — the sanctioned wiring proof.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

# Make the kernel + ingest packages importable when run as a bare script.
TIERVA = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TIERVA not in sys.path:
    sys.path.insert(0, TIERVA)

from kernel.climatology import zscore_anomaly
from kernel.consensus import apply_consensus_trigger, composite_signal

# Pacto Seco data_cache holding the previously-loaded Sentinel-2 NDVI parquets
# (output of ingest.sources.sentinel2.ndvi_timeseries) for the Honduras AOIs.
DATA_CACHE = (
    "/Users/broodierchip-m1air/Documents/Hackthon/taikai/projects/"
    "copernicuslac-seguridad-alimentaria-2026/pacto-seco/data_cache"
)

# Known-drought AOI: Concepcion de Maria, Honduras (the cleanest cached case).
HONDURAS_AOI = "ConcepcióndeMaria"
BASELINE_YEARS = [2019, 2020, 2021, 2022]  # climatological normal
DROUGHT_YEAR = 2023  # the el-Nino drought year -> must FIRE
GREEN_YEAR = 2021    # the greenest cached year -> must NOT fire

# California Central Valley parcel (the proven-fast live pull target).
CA_PARCEL_BOUNDS = (-119.7025, 36.5975, -119.6975, 36.6025)

# Network-IO errors that mean "runner is offline / PC unreachable", NOT a logic
# bug. We skip (not fail) the live leg on these.
_NETWORK_ERRORS: tuple = (OSError, ConnectionError, TimeoutError)
try:  # add requests/urllib3/rasterio transport errors when importable
    import requests  # type: ignore

    _NETWORK_ERRORS = _NETWORK_ERRORS + (requests.exceptions.RequestException,)
except Exception:  # pragma: no cover - optional
    pass
try:
    import rasterio  # type: ignore

    _NETWORK_ERRORS = _NETWORK_ERRORS + (rasterio.errors.RasterioIOError,)
except Exception:  # pragma: no cover - optional
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_cached_aoi_ndvi(aoi: str) -> pd.DataFrame:
    """Concatenate the per-year cached Sentinel-2 NDVI parquets for an AOI into a
    single multi-year DataFrame[date, ndvi_mean, ...]. Raises if no cache found
    (that is a real environment problem, surfaced not hidden)."""
    parts = []
    for yr in range(2019, 2024):
        path = os.path.join(DATA_CACHE, f"ndvi_{aoi}_{yr}.parquet")
        if os.path.exists(path):
            parts.append(pd.read_parquet(path))
    if not parts:
        raise FileNotFoundError(
            f"No cached NDVI parquets for {aoi} under {DATA_CACHE} "
            "(expected ndvi_{aoi}_YYYY.parquet)."
        )
    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _pipeline_fires(df: pd.DataFrame, target_year: int, baseline_years) -> pd.DataFrame:
    """The FULL kernel pipeline on a value series: zscore anomaly vs the
    multi-year monthly climatology -> composite_signal (single-sensor NDVI
    passthrough -> 'signal') -> apply_consensus_trigger with contract defaults.
    Returns the trigger frame restricted to the target year."""
    anom = zscore_anomaly(
        df, "ndvi_mean", baseline_years=baseline_years, out_col="ndvi_anomaly"
    )
    target = anom[anom["date"].dt.year == target_year].copy()
    # Route the lone NDVI anomaly through the named composite engine. With one
    # sensor it is a passthrough: 'signal' == 'ndvi_anomaly'. This exercises the
    # composite code path that the multi-sensor production trigger uses.
    target = composite_signal(target, weights={"ndvi_anomaly": 1.0})
    # Single-sensor NDVI-only consensus (the sanctioned wiring proof). All other
    # params are the contract defaults (threshold -1.2, persistence 20, gap 14,
    # confirmations 3) inherited from ConsensusConfig.
    return apply_consensus_trigger(target, sensors=["signal"], min_sensors=1)


# ---------------------------------------------------------------------------
# OFFLINE assertions (always run; gate CI) — cached multi-year drought decision
# ---------------------------------------------------------------------------
def test_drought_year_fires():
    """Known DROUGHT (Honduras Concepcion 2023, baseline 2019-2022) -> FIRES.

    Live-loaded-then-cached real Sentinel-2 NDVI, full kernel pipeline, contract
    defaults. The 2023 el-Nino drought drives NDVI well below the multi-year
    monthly normal -> a sustained consensus run -> the trigger fires.
    """
    df = _load_cached_aoi_ndvi(HONDURAS_AOI)
    out = _pipeline_fires(df, DROUGHT_YEAR, BASELINE_YEARS)
    fired = bool(out["triggered"].any())
    min_anom = float(out["ndvi_anomaly"].min())
    assert fired is True, (
        f"DROUGHT {DROUGHT_YEAR} should FIRE; it did not. "
        f"min anomaly={min_anom:.2f}, breaching scenes="
        f"{int((out['ndvi_anomaly'] <= -1.2).sum())}"
    )
    # Sanity: the drought genuinely depresses NDVI (negative anomalies present).
    assert min_anom <= -1.2, f"expected breaching anomalies, min was {min_anom:.2f}"


def test_green_year_does_not_fire():
    """NORMAL/GREEN year (same AOI + SAME baseline 2019-2022, target 2021) -> NO fire.

    2021 is the greenest cached year (highest median NDVI): its anomalies sit at
    or above the normal, so the SAME pipeline with the SAME baseline does not
    sustain a below-threshold consensus run and does NOT fire. Only the target
    year differs from the drought case above.
    """
    df = _load_cached_aoi_ndvi(HONDURAS_AOI)
    out = _pipeline_fires(df, GREEN_YEAR, BASELINE_YEARS)
    fired = bool(out["triggered"].any())
    median_anom = float(out["ndvi_anomaly"].median())
    assert fired is False, (
        f"GREEN year {GREEN_YEAR} should NOT fire; it did. "
        f"median anomaly={median_anom:.2f}"
    )


# ---------------------------------------------------------------------------
# LIVE leg (network) — real loader -> kernel on freshly-downloaded bytes
# ---------------------------------------------------------------------------
def test_live_loader_to_kernel_california():
    """LIVE: ndvi_timeseries (network) -> zscore_anomaly -> composite_signal ->
    apply_consensus_trigger on the California parcel, July 2023, cloud<20.

    Proves the full loader->climatology->consensus path executes on bytes pulled
    over the network THIS RUN. A single calendar month cannot form a multi-year
    climatology, so the anomaly is only a within-month z-score (NOT a meaningful
    multi-year drought anomaly) — the point is the LIVE wiring + a finite real
    NDVI series, not a payout decision.

    Skipped (not failed) on a network/IO error so an outage is not a regression.
    """
    from shapely.geometry import box

    from ingest.sources.sentinel2 import ndvi_timeseries

    parcel = box(*CA_PARCEL_BOUNDS)
    ndvi = ndvi_timeseries(parcel, "2023-07-01", "2023-07-31", max_cloud=20)

    assert not ndvi.empty, "live NDVI pull returned no scenes for July 2023"
    assert np.isfinite(ndvi["ndvi_mean"]).all(), "live NDVI contained non-finite values"
    # Central Valley cropland in July: NDVI plausibly in (0, 1).
    assert 0.0 < float(ndvi["ndvi_mean"].mean()) < 1.0, (
        f"live NDVI mean out of plausible range: {ndvi['ndvi_mean'].mean()}"
    )

    # Full kernel path on the live bytes (degenerate single-month climatology).
    anom = zscore_anomaly(
        ndvi, "ndvi_mean", baseline_years=[2023], out_col="ndvi_anomaly"
    )
    anom = composite_signal(anom, weights={"ndvi_anomaly": 1.0})
    out = apply_consensus_trigger(anom, sensors=["signal"], min_sensors=1)
    # The trigger frame must come back fully formed from real-data input.
    for col in ("breach", "confirmations", "triggered"):
        assert col in out.columns, f"kernel output missing column {col!r}"
    assert len(out) == len(ndvi), "kernel dropped/added rows vs the live series"


def _all_tests():
    g = globals()
    return [g[n] for n in sorted(g) if n.startswith("test_") and callable(g[n])]


_LIVE_TESTS = {"test_live_loader_to_kernel_california"}


if __name__ == "__main__":
    network_on = os.environ.get("RUN_NETWORK_TESTS") == "1"
    failures = []
    skipped = []
    for fn in _all_tests():
        is_live = fn.__name__ in _LIVE_TESTS
        if is_live and not network_on:
            skipped.append(fn.__name__)
            print(f"  SKIP  {fn.__name__}  (network gate: set RUN_NETWORK_TESTS=1)")
            continue
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except _NETWORK_ERRORS as exc:  # outage on the live leg -> skip, not fail
            if is_live:
                skipped.append(fn.__name__)
                print(f"  SKIP  {fn.__name__}  (network error: {exc!r})")
            else:
                failures.append((fn.__name__, exc))
                print(f"  FAIL  {fn.__name__}: {exc!r}")
        except Exception as exc:  # noqa: BLE001 — surface every logic failure
            failures.append((fn.__name__, exc))
            print(f"  FAIL  {fn.__name__}: {exc!r}")

    n = len(_all_tests())
    if failures:
        raise SystemExit(f"{len(failures)} test(s) FAILED")
    if not network_on:
        print(
            f"\nOFFLINE PASS ({n - len(skipped)}/{n}); "
            f"{len(skipped)} network test(s) SKIPPED (set RUN_NETWORK_TESTS=1)"
        )
    else:
        print(f"\nALL PASS ({n - len(skipped)}/{n}); {len(skipped)} skipped")
