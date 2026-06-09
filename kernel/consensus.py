"""Multi-sensor consensus engine — domain-agnostic parametric trigger.

The core product: no single sensor can fire a payout. Each sensor contributes a
standardized anomaly column; a trigger requires >= min_sensors to AGREE
(each on the breaching side of `threshold`) and to STAY in agreement across a
continuous run that spans >= persistence_days AND is confirmed by
>= min_confirmations separate qualifying scenes, with no unobserved gap longer
than max_gap_days inside the run.

Lifted and generalized from Pacto Seco's DCSI (composite_dcsi /
consensus_count / apply_consensus_trigger):
  * 'dcsi' -> 'signal', 'drought'/'in_drought' -> 'breach', 'consensus' -> 'breach'
  * the hardwired drought menu (NDVI/SPI-3/SAR/FAPAR) -> caller supplies columns
  * the hardwired '<= threshold' comparator -> a `direction` param ("below" =
    breach when value <= threshold, for drought/greenness; "above" = breach
    when value >= threshold, for flood/heat). The comparator lives in ONE
    helper and is applied at BOTH sites (consensus_count AND the trigger loop).
  * all drought-tuned module constants -> a ConsensusConfig dataclass / params.

*** FIRING-PREDICATE UNIFICATION WITH THE ON-CHAIN CONTRACT ***
This kernel is the off-chain simulator of the on-chain rule. The Solidity
contract (PactoSeco.sol `_report`) is the SOURCE OF TRUTH because money moves
there, and it fires only when ALL of:
    (dayIndex - runStart) >= CONSENSUS_DAYS (20)            # span
    confirmations         >= MIN_CONFIRMATIONS (3)          # # qualifying scenes
    no gap since lastQualifyingDay > MAX_GAP_DAYS (14)      # else restart run
A gap > MAX_GAP_DAYS restarts the run AND resets confirmations to 1. An
above/non-breaching reading breaks the run and resets confirmations to 0.

The original kernel was WEAKER (span-only, no confirmations count, max_gap 35).
This port adds the confirmations counter and matches the contract defaults
(persistence_days=20, max_gap_days=14, min_confirmations=3) so a backtest that
looks safe here behaves the same way on-chain.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Contract-matching defaults (PactoSeco.sol):
#   CONSENSUS_DAYS = 20, MIN_CONFIRMATIONS = 3, MAX_GAP_DAYS = 14,
#   MIN_SENSOR_CONSENSUS = 2, TRIGGER_THRESHOLD = -1.20 (scaled -120 on-chain).
DEFAULT_THRESHOLD = -1.2
DEFAULT_MIN_SENSORS = 2
DEFAULT_PERSISTENCE_DAYS = 20
DEFAULT_MAX_GAP_DAYS = 14
DEFAULT_MIN_CONFIRMATIONS = 3
DEFAULT_DIRECTION = "below"


@dataclass
class ConsensusConfig:
    """Parametric trigger config. Defaults mirror the on-chain contract.

    threshold        : anomaly cut a sensor must reach to count as breaching.
    min_sensors      : independent sensors that must agree in a single scene
                       (on-chain MIN_SENSOR_CONSENSUS).
    persistence_days : run must SPAN at least this many days (CONSENSUS_DAYS).
    max_gap_days     : a gap longer than this between qualifying scenes restarts
                       the run and resets confirmations (MAX_GAP_DAYS).
    min_confirmations: a run must have at least this many qualifying scenes to
                       fire (MIN_CONFIRMATIONS).
    direction        : "below" -> breach when value <= threshold (drought,
                       greenness, rainfall deficit); "above" -> breach when
                       value >= threshold (flood level, heat).
    sensors          : the anomaly columns that count toward consensus. None =>
                       a single column named "signal".
    """
    threshold: float = DEFAULT_THRESHOLD
    min_sensors: int = DEFAULT_MIN_SENSORS
    persistence_days: int = DEFAULT_PERSISTENCE_DAYS
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS
    min_confirmations: int = DEFAULT_MIN_CONFIRMATIONS
    direction: str = DEFAULT_DIRECTION
    sensors: list | None = None


def _breach_mask(values, threshold: float, direction: str):
    """The single comparator used at BOTH consensus sites.

    Returns a boolean of where `values` breach `threshold` given `direction`:
      "below" -> values <= threshold   (drought / lower-is-worse)
      "above" -> values >= threshold   (flood / heat / higher-is-worse)
    """
    if direction == "below":
        return values <= threshold
    if direction == "above":
        return values >= threshold
    raise ValueError(f"direction must be 'below' or 'above', got {direction!r}")


def composite_signal(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Weighted blend of available anomaly columns -> 'signal'.

    Per-row renormalization over PRESENT (non-NaN) sensors so that a missing
    sensor doesn't dilute a real anomaly toward 0. `den` is the sum of weights
    of sensors observed on that row; an all-NaN row -> den 0 -> signal NaN.

    (Generalized from composite_dcsi; the output column is 'signal' not 'dcsi'.)
    """
    df = df.copy()
    weights = weights or {"signal": 1.0}
    avail = {k: w for k, w in weights.items() if k in df.columns}
    num = pd.Series(0.0, index=df.index)
    den = pd.Series(0.0, index=df.index)
    for k, w in avail.items():
        num = num + df[k].fillna(0) * w
        den = den + df[k].notna() * w
    df["signal"] = num / den.replace(0, np.nan)
    return df


def consensus_count(
    df: pd.DataFrame,
    threshold: float = DEFAULT_THRESHOLD,
    sensors=None,
    direction: str = DEFAULT_DIRECTION,
) -> pd.DataFrame:
    """Add per-row 'sensors_available' and 'sensors_in_breach'.

    A sensor is "in breach" when its anomaly breaches `threshold` on the side
    given by `direction` (see _breach_mask). The comparator here is the SAME
    one used in the trigger loop.

    sensors selects which anomaly columns count; None -> the single column
    "signal".
    """
    df = df.copy()
    candidate = sensors if sensors is not None else ["signal"]
    cols = [c for c in candidate if c in df.columns]
    if not cols:
        df["sensors_available"] = 0
        df["sensors_in_breach"] = 0
        return df
    df["sensors_available"] = df[cols].notna().sum(axis=1)
    df["sensors_in_breach"] = _breach_mask(df[cols], threshold, direction).sum(axis=1)
    return df


def apply_consensus_trigger(
    df: pd.DataFrame,
    config: ConsensusConfig | None = None,
    *,
    threshold: float | None = None,
    min_sensors: int | None = None,
    persistence_days: int | None = None,
    max_gap_days: int | None = None,
    min_confirmations: int | None = None,
    direction: str | None = None,
    sensors=None,
    date_col: str = "date",
) -> pd.DataFrame:
    """Fire only on a genuine continuous consensus run, matching PactoSeco._report.

    A row qualifies (is a "breach" scene) when >= min_sensors agree
    (each anomaly breaches `threshold` on the `direction` side). The contract's
    firing predicate is replicated exactly — and, critically, so is its
    THREE-WAY treatment of a row by how many sensors breach:

      - QUALIFYING row (sensors_in_breach >= min_sensors):
          * start a FRESH run if there is none OR the gap since the previous
            qualifying row > max_gap_days -> run_start = date, confirmations = 1
          * otherwise -> confirmations += 1
          * FIRE iff (date - run_start).days >= persistence_days
                 AND confirmations >= min_confirmations
      - SUB-CONSENSUS row (0 < sensors_in_breach < min_sensors):
          * NO state change — the run is NOT reset and NOT advanced. This mirrors
            the on-chain mechanism where a sub-consensus scene posted via
            reportDailyMulti REVERTS "consensus not met" with no state change
            (oracle.py header, "IMPORTANT (mechanism)"): it neither breaks nor
            resets the run. A lone-sensor dip during an otherwise-quiet stretch
            therefore does not, by itself, knock the contract's run back to zero.
      - GENUINE NON-BREACH row (sensors_in_breach == 0):
          * reset run (run_start = None, confirmations = 0). This is the
            non-breaching reading the contract receives via reportDaily, which
            DOES break the run.

    Why the distinction matters (the audit finding): treating EVERY
    non-qualifying row as a reset conflates a sub-consensus row (which the
    contract ignores) with a true non-breach row (which the contract resets on).
    That makes this kernel UNDER-fire relative to the contract — a backtest that
    looks "safe" here could still fire on-chain. Splitting the two realigns the
    off-chain simulator with the on-chain source of truth.

    Note the gap is measured against the previous QUALIFYING row (which is what
    `prev_date` tracks, since it only advances on qualifying rows) — this equals
    the contract's `lastQualifyingDay`. `> max_gap_days` is strict: a 14-day gap
    continues the run, a 15-day gap restarts it (matching
    `dayIndex - lastQualifyingDay > MAX_GAP_DAYS`).

    Divergence from the contract (intentional, equivalent for a fire/no-fire
    backtest): the contract latches `disbursed` so a season fires once and
    reverts on non-increasing dayIndex; this kernel marks EVERY qualifying row
    that meets the predicate. For the predicate `df["triggered"].any()` the two
    are equivalent.

    CADENCE CAVEAT: with max_gap_days=14 and persistence_days=20, spanning >=20
    days already requires >=3 qualifying scenes (2 scenes span <= 14 < 20), so
    the confirmations check is co-satisfied at the default params — it bites
    under other params (e.g. denser cadence or larger gap tolerance). It is kept
    for exact contract fidelity.

    Pass a ConsensusConfig OR individual keyword overrides (overrides win).
    """
    cfg = config or ConsensusConfig()
    threshold = cfg.threshold if threshold is None else threshold
    min_sensors = cfg.min_sensors if min_sensors is None else min_sensors
    persistence_days = cfg.persistence_days if persistence_days is None else persistence_days
    max_gap_days = cfg.max_gap_days if max_gap_days is None else max_gap_days
    min_confirmations = cfg.min_confirmations if min_confirmations is None else min_confirmations
    direction = cfg.direction if direction is None else direction
    sensors = cfg.sensors if sensors is None else sensors

    df = consensus_count(df, threshold, sensors, direction)
    df = df.sort_values(date_col).copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["breach"] = df["sensors_in_breach"] >= min_sensors

    triggered = np.zeros(len(df), dtype=bool)
    confirmations_col = np.zeros(len(df), dtype=int)
    run_start = None
    prev_date = None  # last QUALIFYING date == contract lastQualifyingDay
    confirmations = 0
    for i, row in df.reset_index(drop=True).iterrows():
        if row["breach"]:
            # QUALIFYING row: >= min_sensors agree -> advance (or start) the run.
            if run_start is None or (row[date_col] - prev_date).days > max_gap_days:
                run_start = row[date_col]
                confirmations = 1
            else:
                confirmations += 1
            prev_date = row[date_col]
            confirmations_col[i] = confirmations
            if (
                (row[date_col] - run_start).days >= persistence_days
                and confirmations >= min_confirmations
            ):
                triggered[i] = True
        elif row["sensors_in_breach"] > 0:
            # SUB-CONSENSUS row: at least one sensor breached but fewer than
            # min_sensors. The contract REVERTS such a scene with no state change
            # (reportDailyMulti "consensus not met"), so the run is neither reset
            # nor advanced here. We carry the current confirmations forward for
            # honest display only (cosmetic; the run state is untouched).
            confirmations_col[i] = confirmations
        else:
            # GENUINE NON-BREACH row: zero sensors breach -> reset the run, the
            # same way the contract's reportDaily non-breaching path does.
            run_start = None
            prev_date = None
            confirmations = 0
    df["confirmations"] = confirmations_col
    df["triggered"] = triggered
    return df


def first_trigger_date(df: pd.DataFrame, date_col: str = "date"):
    """First date at which the trigger fired, or None."""
    t = df[df["triggered"]]
    return None if t.empty else t.iloc[0][date_col]
