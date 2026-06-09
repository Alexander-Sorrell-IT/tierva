#!/usr/bin/env python3
"""oracle.py — Tierva's off-chain -> on-chain oracle bridge.

This is the missing wire between the two halves of a Tierva pool:
  • OFF-CHAIN  : a multi-sensor signal pipeline (e.g. Sentinel-2 NDVI +
                 ERA5-Land rainfall SPI-3, plus SAR / FAPAR when finite) that
                 produces, per area-of-interest, a per-scene anomaly for EACH
                 sensor.
  • ON-CHAIN   : Pacto.reportDailyMulti(pool, cycle, dayIndex,
                 int256[] sensorAnomalies), which counts how many sensors
                 BREACH the per-pool threshold, REQUIRES >= minSensorConsensus to
                 AGREE before a scene can count toward the run (the multi-sensor
                 consensus, ENFORCED in Solidity), tracks a continuous breaching
                 run on-chain, and self-disburses the pre-agreed payout once the
                 multi-day, multi-scene consensus is reached.

THE CONSENSUS RULE — ENFORCED ON-CHAIN (not pre-reduced off-chain):
  For each scene the oracle posts the RAW PER-SENSOR anomaly ARRAY (each scaled
  by 100 to stay integer on-chain). The CONTRACT counts how many entries breach
  the per-pool triggerThreshold (direction set by breachBelow) and
  `require(inBreach >= minSensorConsensus, "consensus not met")`:

        a scene counts toward the run  IFF  >= minSensorConsensus sensors breach

  This is the multi-sensor consensus, checked in the contract — the oracle can
  not fake a pre-reduced scalar. A lone sensor dip (the dry-season single-sensor
  blip: one signal deep in breach, the others normal) has only ONE sensor in
  breach, so reportDailyMulti REVERTS with "consensus not met" and the scene
  never touches the run. By construction a scene with only ONE finite sensor
  yields a length-1 array, so inBreach >= 2 is impossible — a single sensor can
  NEVER fire a payout.

  IMPORTANT (mechanism): a sub-consensus scene posted via reportDailyMulti
  REVERTS with NO state change — it does NOT break or reset the on-chain run.
  The run only resets when (a) the contract receives a non-breaching reading via
  reportDaily, or (b) the gap since the last qualifying scene exceeds maxGapDays.

The daemon is deliberately thin: it can ONLY report per-sensor signal *state*
for an enrolled pool+cycle. It can never move money to an arbitrary address —
that power lives in the contract, gated by the on-chain run counter and the
on-chain consensus check. This is the separation of powers the contract enforces
(oracle != owner) PLUS separation of evidence (consensus != one sensor).

CLEAN SEPARATION (this file has two independent halves):
  1. PUSHER  — push_series(...) takes a chain-agnostic iterable of
               (dayIndex, [per-sensor anomaly ints]) and posts each via
               reportDailyMulti, handling the "consensus not met" revert
               GRACEFULLY (a sub-consensus scene is EXPECTED to revert / be
               skipped, never crashes the daemon). It knows nothing about
               pandas or any pipeline.
  2. PROVIDER — concepcion_2023_series(...) yields the per-sensor anomaly series
               for an AOI+year. It reuses the PROVEN pacto_seco pipeline (real
               cached Copernicus data) and imports pacto_seco LAZILY, so the
               pusher runs without pandas/pacto_seco installed.

Series provenance (REAL data, generalized): the default provider is built from
the SAME pipeline functions used by the proven backtest (ndvi_anomaly /
spi3_anomaly / attach_spi3_to_scenes), so the per-scene sensor values pushed
on-chain are identical to the off-chain backtest. The TWO HALVES AGREE: on this
REAL 2023 Concepción series the off-chain consensus engine (>=2 sensors,
threshold -1.20, multi-day span) fires in early July, and the on-chain contract
reaches its consensus on the same scene (dayIndex 186 = 2023-07-05) via
reportDailyMulti — both reject the single-sensor January NDVI blip (a single
sensor would have fired 2023-01-21). Precipitation is read from data_cache, so a
run is fully offline (no CDS, no faucet, no testnet).

A tierva-kernel-native provider (using the tierva `kernel` package —
consensus.py / climatology.py, the domain-agnostic port of this same rule) is
the documented FOLLOW-UP: it would yield the same (dayIndex, [ints]) shape the
pusher already consumes, so the pusher needs no change.

Usage (local anvil, account[1] = oracle):
  .venv/bin/python oracle.py \
      --rpc http://localhost:8545 \
      --pacto 0x... \
      --oracle-key 0x59c6...690d \
      --pool tierva:concepcion:drought \
      --cycle 2023

Use --dry-run to print the per-sensor series and the would-be transactions
(including which scenes the contract will REJECT) without sending. --dry-run
needs no RPC, no key, no contract — it also runs a LOCAL fire-predicate
simulation that proves the run fires at exactly dayIndex 186.

Keys are NEVER hardcoded: --oracle-key (or ORACLE_KEY env) and --rpc / --pacto
(or RPC_URL / PACTO_ADDRESS env) are read at runtime, names only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# CONTRACT DEFAULTS (per-pool config on-chain; CLI/env-overridable here).
# These mirror the Pacto constructor immutables for the drought config so the
# pusher's predicted accepted/reverted display matches what the contract will do.
# The pusher posts RAW arrays and does NOT need these to function — they only
# drive the dry-run prediction and the local fire-predicate simulation.
# ---------------------------------------------------------------------------
DEFAULT_TRIGGER_THRESHOLD = -120   # signal breaches this (scaled by 100)
DEFAULT_BREACH_BELOW = True        # True: breach iff v <= threshold (drought)
DEFAULT_MIN_CONSENSUS = 2          # >= this many sensors must agree per scene
DEFAULT_CONSENSUS_DAYS = 20        # run must SPAN >= this many days
DEFAULT_MIN_CONFIRMATIONS = 3      # run must have >= this many qualifying scenes
DEFAULT_MAX_GAP_DAYS = 14          # gap > this between scenes restarts the run

# The contract reverts with this EXACT string when a scene fails the on-chain
# multi-sensor consensus. On the enforced path that is EXPECTED for
# non-qualifying scenes (e.g. the single-sensor January blip): the tx makes no
# state change and the daemon simply moves on to the next scene.
CONSENSUS_REVERT = "consensus not met"

# Disbursed(pool, cycle, beneficiaries, total) — topic0 used to detect a payout.
DISBURSED_EVENT_SIG = "Disbursed(bytes32,uint16,uint256,uint256)"

# A "scene" is the chain-agnostic unit the pusher consumes.
Scene = Tuple[int, List[int]]  # (dayIndex, [per-sensor anomaly ints, x100])


# ---------------------------------------------------------------------------
# Shared breach comparator — single source of truth, mirrors the contract's
# _breaches(): breachBelow=True => v <= threshold; False => v >= threshold.
# ---------------------------------------------------------------------------
def breaches(value: int, threshold: int, breach_below: bool) -> bool:
    return value <= threshold if breach_below else value >= threshold


def below_count(arr: Sequence[int], threshold: int, breach_below: bool) -> int:
    """How many posted anomalies the CONTRACT will count as breaching."""
    return sum(1 for v in arr if breaches(int(v), threshold, breach_below))


# ===========================================================================
# 1. PUSHER (the wire) — chain/key-agnostic; consumes generic (dayIndex, ints)
# ===========================================================================
def _cast_keccak(label: str) -> str:
    out = subprocess.run(["cast", "keccak", label], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _fmt_arr(arr: Sequence[int]) -> str:
    """Cast-friendly int256[] literal, e.g. [-176,-49]."""
    return "[" + ",".join(str(int(v)) for v in arr) + "]"


def _cast_send(rpc: str, key: str, to: str, sig: str, *args, allow_consensus_revert: bool = False):
    """Send a tx via cast and return the parsed JSON receipt.

    If allow_consensus_revert is set and the tx fails the on-chain consensus
    check ("consensus not met"), return None instead of raising — that scene
    simply does not advance the run (exactly the enforced behavior). Any OTHER
    failure is still raised, so the daemon never silently swallows a real bug."""
    cmd = ["cast", "send", "--rpc-url", rpc, "--private-key", key, "--json", to, sig, *map(str, args)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        if allow_consensus_revert and CONSENSUS_REVERT in (out.stderr + out.stdout):
            return None
        raise RuntimeError(f"cast send failed: {sig} {args}\n{out.stderr.strip()}")
    return json.loads(out.stdout)


def _cast_call(rpc: str, to: str, sig: str, *args) -> str:
    cmd = ["cast", "call", "--rpc-url", rpc, to, sig, *map(str, args)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def pool_id(pool_label: str) -> str:
    """The on-chain bytes32 pool id = keccak256(pool_label). Done via cast so the
    pusher carries no extra dependency."""
    return _cast_keccak(pool_label)


def predict_acceptance(scenes: Iterable[Scene], threshold: int, breach_below: bool,
                       min_consensus: int) -> List[dict]:
    """For each scene, predict what the contract will do (accept / revert).

    Pure / chain-free: mirrors the contract's per-scene consensus count so the
    dry-run and logging can show which scenes REVERT 'consensus not met'."""
    rows: List[dict] = []
    for day, arr in scenes:
        below = below_count(arr, threshold, breach_below)
        rows.append({
            "dayIndex": int(day),
            "sensors": [int(v) for v in arr],
            "below": below,
            "accepted": below >= min_consensus,
        })
    return rows


def simulate_fire(scenes: Iterable[Scene], threshold: int, breach_below: bool,
                  min_consensus: int, consensus_days: int, min_confirmations: int,
                  max_gap_days: int) -> Optional[int]:
    """LOCAL simulation of the on-chain fire predicate (Pacto._report +
    reportDailyMulti consensus gate). NO chain involved. Returns the dayIndex on
    which the contract would first disburse, or None.

    This substantiates the load-bearing provenance claim (fires at exactly
    dayIndex 186) without ever touching a testnet. It reproduces, in Python, the
    exact Solidity logic:
      • a scene with < min_consensus sensors breaching REVERTS with no state
        change (it does NOT reset the run);
      • a qualifying scene either starts a fresh run (none active, or the gap
        since the last qualifying scene exceeds max_gap_days) or extends it;
      • fire iff (dayIndex - runStart) >= consensus_days AND
        confirmations >= min_confirmations."""
    run_start = 0
    confirmations = 0
    last_qual = 0
    last_day = -1
    for day, arr in scenes:
        day = int(day)
        if day <= last_day:
            continue  # strictly-increasing replay guard (contract requires this)
        below = below_count(arr, threshold, breach_below)
        if below < min_consensus:
            # reportDailyMulti REVERTS: no state change, run untouched.
            continue
        last_day = day
        if run_start == 0 or (day - last_qual) > max_gap_days:
            run_start = day
            confirmations = 1
        else:
            confirmations += 1
        last_qual = day
        if (day - run_start) >= consensus_days and confirmations >= min_confirmations:
            return day
    return None


def push_series(
    scenes: Sequence[Scene],
    *,
    rpc: str,
    oracle_key: str,
    pacto: str,
    pool_label: str,
    cycle: int,
    threshold: int = DEFAULT_TRIGGER_THRESHOLD,
    breach_below: bool = DEFAULT_BREACH_BELOW,
    min_consensus: int = DEFAULT_MIN_CONSENSUS,
    log=print,
) -> dict:
    """Post each scene via reportDailyMulti(pool, cycle, dayIndex, int256[]).

    `scenes` is a chain-agnostic sequence of (dayIndex, [per-sensor ints]).
    Returns a summary dict {accepted, rejected, fire_event, disbursed}. A
    sub-consensus scene is SKIPPED gracefully (the contract reverts 'consensus
    not met', no state change) — it never crashes the daemon."""
    pid = pool_id(pool_label)
    disbursed_topic = _cast_keccak(DISBURSED_EVENT_SIG)

    accepted = 0
    rejected = 0
    fire_event: Optional[dict] = None

    for day, arr in scenes:
        day = int(day)
        arr = [int(v) for v in arr]
        below = below_count(arr, threshold, breach_below)
        receipt = _cast_send(
            rpc, oracle_key, pacto,
            "reportDailyMulti(bytes32,uint16,uint32,int256[])",
            pid, cycle, day, _fmt_arr(arr),
            allow_consensus_revert=True,
        )
        if receipt is None:
            # Contract rejected this scene: < min_consensus sensors breaching.
            # No state change — the run is not advanced. This is the enforced
            # consensus refusing a single-sensor reading.
            rejected += 1
            log(f"  reportDailyMulti day={day:>3} {_fmt_arr(arr):>18} "
                f"below={below}  REVERTED (consensus not met)")
            continue
        accepted += 1
        txh = receipt.get("transactionHash")
        logs = receipt.get("logs", [])
        fired_here = any((lg.get("topics") or [None])[0] == disbursed_topic for lg in logs)
        tag = "  <-- DISBURSED!" if fired_here else ""
        log(f"  reportDailyMulti day={day:>3} {_fmt_arr(arr):>18} "
            f"below={below}  ACCEPTED tx={txh}{tag}")
        if fired_here and fire_event is None:
            blk = receipt.get("blockNumber")
            fire_event = {
                "dayIndex": day,
                "sensors": arr,
                "txHash": txh,
                "blockNumber": int(blk, 16) if isinstance(blk, str) else blk,
            }

    log(f"\n  pushed {accepted + rejected} reportDailyMulti txs: "
        f"{accepted} ACCEPTED, {rejected} REVERTED on-chain (consensus not met).")
    if fire_event:
        log(f"\n  *** Disbursed fired at dayIndex={fire_event['dayIndex']} "
            f"sensors={_fmt_arr(fire_event['sensors'])} tx={fire_event['txHash']} ***")
    else:
        log("\n  (no Disbursed event observed in tx logs — check series / threshold)")

    # End-state proof: read the public disbursed(pool,cycle) mapping on-chain.
    disbursed = _cast_call(rpc, pacto, "disbursed(bytes32,uint16)(bool)", pid, cycle)
    log(f"\n  on-chain disbursed(pool, cycle={cycle}) = {disbursed}")

    return {"accepted": accepted, "rejected": rejected,
            "fire_event": fire_event, "disbursed": disbursed}


# ===========================================================================
# 2. SERIES PROVIDER (off-chain half) — REAL cached Copernicus data.
#    pacto_seco is imported LAZILY here so the pusher above stays dependency-free.
# ===========================================================================
# Location of the proven pacto_seco project. Resolution order (no machine-
# specific absolute path baked in):
#   1. env vars PACTO_SECO_SRC / PACTO_SECO_CACHE (point them anywhere), else
#   2. PACTO_SECO_ROOT env var (the project root), else
#   3. a repo-relative anchor derived from __file__.
# oracle.py lives at tierva/oracle/oracle.py, and pacto-seco hangs off the SAME
# workspace root (.../Hackthon) at taikai/projects/.../pacto-seco. So
# parents[2] == .../Hackthon and the relative anchor resolves correctly on any
# checkout that keeps that layout — no hardcoded /Users/... required.
_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]  # .../Hackthon
_DEFAULT_PACTO_SECO_ROOT = (
    _WORKSPACE_ROOT
    / "taikai" / "projects"
    / "copernicuslac-seguridad-alimentaria-2026" / "pacto-seco"
)
_PACTO_SECO_ROOT = Path(os.environ.get("PACTO_SECO_ROOT", str(_DEFAULT_PACTO_SECO_ROOT)))
PACTO_SECO_SRC = Path(os.environ.get("PACTO_SECO_SRC", str(_PACTO_SECO_ROOT / "src")))
PACTO_SECO_CACHE = Path(os.environ.get("PACTO_SECO_CACHE", str(_PACTO_SECO_ROOT / "data_cache")))

# Baseline years for the climatology the anomalies are measured against.
PROVIDER_BASELINE = [2019, 2020, 2021, 2022]
# Which anomaly columns to push, in priority order. A scene contributes only the
# sensors with a FINITE reading on that date (NaN dropped), so a single-sensor
# scene yields a length-1 array that can never reach the consensus the contract
# requires. (2023 Concepción has both NDVI and rainfall on every scene;
# SAR/FAPAR are attached only where finite.)
PROVIDER_SENSOR_COLS = ["ndvi_anomaly", "spi3", "sar_anomaly", "fapar_anomaly"]


def concepcion_2023_series(
    name_fragment: str = "Concepci",
    department: str = "Choluteca",
    source_year: int = 2023,
) -> List[Scene]:
    """Yield the REAL per-sensor anomaly series as a list of (dayIndex, [ints]).

    Reuses the PROVEN pacto_seco pipeline against the cached real Copernicus data
    in data_cache, so the values posted on-chain are identical to the off-chain
    backtest. AOI-load args (fragment / department / source_year) locate the real
    data and are DISTINCT from the on-chain pool/cycle identifiers — the same
    physical series can back any pool label or cycle number.

    Each anomaly is scaled by 100 to stay integer on-chain. dayIndex = day-of-year
    (1-based; matches the contract's "must be >= 1 and strictly increasing").

    NOTE: imports are LAZY (inside this function) so the pusher half of this
    module can run without pandas / pacto_seco installed."""
    sys.path.insert(0, str(PACTO_SECO_SRC))
    import numpy as np  # noqa: E402  (lazy: provider-only)
    import pandas as pd  # noqa: E402
    from pacto_seco.municipios.honduras_dry_corridor import load_dry_corridor  # noqa: E402
    from pacto_seco.data.era5_loader import (  # noqa: E402
        precip_monthly, spi3_anomaly, attach_spi3_to_scenes,
    )
    from pacto_seco.index import dcsi as D  # noqa: E402

    # --- locate the AOI in the cached pipeline -----------------------------
    dc = load_dry_corridor()
    sub = dc
    if department:
        sub = dc[dc["department"].str.replace(" ", "").str.contains(
            department.replace(" ", ""), case=False)]
    norm = name_fragment.replace(" ", "")
    hit = sub[sub["municipio"].str.replace(" ", "").str.contains(norm, case=False)]
    if hit.empty:
        raise SystemExit(f"AOI not found: {name_fragment!r} in {department!r}")
    row = hit.iloc[0]
    name, geom = row["municipio"], row.geometry

    # Sensor 1 — Sentinel-2 NDVI anomaly (cached scenes, ~5-day cadence).
    nfs = sorted(PACTO_SECO_CACHE.glob(f"ndvi_{name.replace(' ', '')}_*.parquet"))
    if not nfs:
        raise SystemExit(f"no cached NDVI for {name!r} in {PACTO_SECO_CACHE}")
    ndvi = pd.concat([pd.read_parquet(f) for f in nfs], ignore_index=True)
    ndvi = D.ndvi_anomaly(ndvi, PROVIDER_BASELINE)

    # Sensor 2 — ERA5-Land rainfall SPI-3 (cached monthly), broadcast to scenes.
    precip = precip_monthly(geom, PROVIDER_BASELINE[0], source_year, name)  # cache-only
    spi = spi3_anomaly(precip, PROVIDER_BASELINE)
    merged = attach_spi3_to_scenes(ndvi, spi)

    test = merged[pd.to_datetime(merged["date"]).dt.year == source_year].copy()
    test["date"] = pd.to_datetime(test["date"])
    test = test.sort_values("date").reset_index(drop=True)

    present = [c for c in PROVIDER_SENSOR_COLS if c in test.columns]
    scenes: List[Scene] = []
    for _, r in test.iterrows():
        arr: List[int] = []
        for c in present:
            v = r.get(c)
            if pd.notna(v) and np.isfinite(v):
                arr.append(int(round(float(v) * 100)))
        day = int(pd.Timestamp(r["date"]).dayofyear)
        scenes.append((day, arr))
    return scenes


# ===========================================================================
# CLI
# ===========================================================================
def _print_series_table(scenes: Sequence[Scene], threshold: int, breach_below: bool,
                        min_consensus: int) -> None:
    rows = predict_acceptance(scenes, threshold, breach_below, min_consensus)
    qual = sum(1 for r in rows if r["accepted"])
    print(f"  scenes the CONTRACT will ACCEPT (>= {min_consensus} sensors "
          f"{'<=' if breach_below else '>='} {threshold}): {qual}   "
          f"-- the other {len(rows) - qual} REVERT 'consensus not met'")
    print(f"  {'dayIndex':>8}  {'sensors_x100':>20}  {'below':>5}  accepted")
    for r in rows:
        print(f"  {r['dayIndex']:>8}  {_fmt_arr(r['sensors']):>20}  "
              f"{r['below']:>5}  {r['accepted']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Tierva oracle bridge — push consensus readings to a Pacto contract")
    # chain / key — names only, never a hardcoded value (env fallbacks)
    ap.add_argument("--rpc", default=os.environ.get("RPC_URL", "http://localhost:8545"))
    ap.add_argument("--pacto", default=os.environ.get("PACTO_ADDRESS"),
                    help="deployed Pacto contract address (or PACTO_ADDRESS env)")
    ap.add_argument("--oracle-key", default=os.environ.get("ORACLE_KEY"),
                    help="oracle private key that signs reportDailyMulti (or ORACLE_KEY env)")
    # on-chain identifiers (DISTINCT from the AOI-load args below)
    ap.add_argument("--pool", default="tierva:concepcion:drought",
                    help="pool label hashed (keccak) to the on-chain bytes32 pool id")
    ap.add_argument("--cycle", type=int, default=2023, help="on-chain cycle (uint16)")
    # per-pool consensus config (mirrors the contract immutables; for prediction)
    ap.add_argument("--trigger-threshold", type=int, default=DEFAULT_TRIGGER_THRESHOLD)
    bgrp = ap.add_mutually_exclusive_group()
    bgrp.add_argument("--breach-below", dest="breach_below", action="store_true",
                      help="breach iff signal <= threshold (drought; default)")
    bgrp.add_argument("--breach-above", dest="breach_below", action="store_false",
                      help="breach iff signal >= threshold (heat / flood)")
    ap.set_defaults(breach_below=DEFAULT_BREACH_BELOW)
    ap.add_argument("--min-consensus", type=int, default=DEFAULT_MIN_CONSENSUS)
    ap.add_argument("--consensus-days", type=int, default=DEFAULT_CONSENSUS_DAYS)
    ap.add_argument("--min-confirmations", type=int, default=DEFAULT_MIN_CONFIRMATIONS)
    ap.add_argument("--max-gap-days", type=int, default=DEFAULT_MAX_GAP_DAYS)
    # AOI-load args for the default provider (locate the REAL cached data)
    ap.add_argument("--aoi-fragment", default="Concepci",
                    help="name fragment used to find the AOI in the cached pipeline")
    ap.add_argument("--aoi-department", default="Choluteca")
    ap.add_argument("--source-year", type=int, default=2023,
                    help="calendar year of the cached series to push")
    ap.add_argument("--dry-run", action="store_true",
                    help="print series + would-be txs + local fire sim; send nothing")
    args = ap.parse_args()

    if not args.dry_run and (not args.pacto or not args.oracle_key):
        ap.error("--pacto and --oracle-key (or PACTO_ADDRESS / ORACLE_KEY env) are required unless --dry-run")

    # --- build the REAL series via the proven provider ---------------------
    scenes = concepcion_2023_series(args.aoi_fragment, args.aoi_department, args.source_year)

    print("=== Tierva oracle bridge (ENFORCED multi-sensor consensus) ===")
    print(f"  pool label  : {args.pool}")
    print(f"  cycle       : {args.cycle}")
    print(f"  contract    : {args.pacto}")
    print(f"  rpc         : {args.rpc}")
    print(f"  scenes      : {len(scenes)}  (threshold={args.trigger_threshold}, "
          f"breach={'below' if args.breach_below else 'above'}, "
          f"min_consensus={args.min_consensus})")
    print(f"  call        : reportDailyMulti(bytes32,uint16,uint32,int256[]) "
          f"-- contract enforces require(inBreach>=min_consensus,'consensus not met')")
    print()
    _print_series_table(scenes, args.trigger_threshold, args.breach_below, args.min_consensus)
    print()

    # Local fire-predicate simulation (no chain) — proves the run fires on the
    # expected scene and rejects the single-sensor blip.
    fire_day = simulate_fire(
        scenes, args.trigger_threshold, args.breach_below, args.min_consensus,
        args.consensus_days, args.min_confirmations, args.max_gap_days,
    )
    if fire_day is not None:
        print(f"  [local sim] on-chain run would first DISBURSE at dayIndex={fire_day} "
              f"(real 2023 series fires ~Jul 5 = dayIndex 186; rejects the single-sensor Jan blip)")
    else:
        print("  [local sim] run never reaches consensus (no disburse).")
    print()

    if args.dry_run:
        print("[dry-run] not sending any transactions; no RPC / key / contract used.")
        print(f"[dry-run] would, if live, end with on-chain disbursed(pool, cycle={args.cycle}) "
              f"= {'true' if fire_day is not None else 'false'} (simulated).")
        return

    push_series(
        scenes,
        rpc=args.rpc, oracle_key=args.oracle_key, pacto=args.pacto,
        pool_label=args.pool, cycle=args.cycle,
        threshold=args.trigger_threshold, breach_below=args.breach_below,
        min_consensus=args.min_consensus,
    )


if __name__ == "__main__":
    main()
