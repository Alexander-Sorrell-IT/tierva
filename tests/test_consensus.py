"""Plain-assert tests for the Tierva consensus kernel (no pytest required).

Run with the Pacto Seco venv (has pandas + numpy):
  /Users/broodierchip-m1air/Documents/Hackthon/taikai/projects/copernicuslac-seguridad-alimentaria-2026/pacto-seco/.venv/bin/python /Users/broodierchip-m1air/Documents/Hackthon/tierva/tests/test_consensus.py

Each scenario mirrors a PactoSeco.sol `_report` case and asserts the SAME
fire/no-fire outcome. Single-signal cases route through apply_consensus_trigger
with sensors=["signal"], min_sensors=1 so the run/gap/confirmations logic is
exercised directly (no separate code path). The trigger predicate under test is
`triggered.any()` == "would this disburse on-chain".
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

# Make the kernel importable when run as a bare script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.climatology import monthly_climatology, zscore_anomaly
from kernel.consensus import (
    ConsensusConfig,
    apply_consensus_trigger,
    composite_signal,
    consensus_count,
    first_trigger_date,
)

EPOCH = pd.Timestamp("2024-01-01")


def days_to_dates(day_indices):
    """Contract dayIndex -> calendar date so .days arithmetic works."""
    return [EPOCH + pd.Timedelta(days=int(d)) for d in day_indices]


def signal_frame(day_indices, signal_values):
    """One 'signal' value per day index."""
    return pd.DataFrame({
        "date": days_to_dates(day_indices),
        "signal": list(signal_values),
    })


def fires(df, **kwargs):
    out = apply_consensus_trigger(df, sensors=["signal"], min_sensors=1, **kwargs)
    return bool(out["triggered"].any())


# --- threshold below which a single 'signal' row counts as a breach.
# Use -1.2 to match the contract's calibrated -1.20 consensus threshold; any
# value at/under this is a breaching scene under direction="below".
THR = -1.2
BREACH = -1.5   # comfortably <= THR  -> qualifies
SAFE = 0.0      # > THR               -> does not qualify


# ---------------------------------------------------------------------------
# Contract-mirroring trigger scenarios (default direction="below")
# ---------------------------------------------------------------------------
def test_single_reading_no_fire():
    """One below-threshold reading -> NO fire (span 0, confirmations 1)."""
    df = signal_frame([100], [BREACH])
    assert fires(df, threshold=THR) is False


def test_21_consecutive_days_fire():
    """21 consecutive daily below-threshold readings (span 20) -> FIRE.

    days 100..120: span = 120-100 = 20 >= 20, gaps all 1 <= 14,
    confirmations = 21 >= 3.
    """
    days = list(range(100, 121))
    df = signal_frame(days, [BREACH] * len(days))
    assert fires(df, threshold=THR) is True


def test_weekly_cadence_fire():
    """Irregular weekly cadence [100,107,114,121]: gaps 7<=14, span 21 -> FIRE.

    confirmations = 4 >= 3, span = 121-100 = 21 >= 20.
    """
    days = [100, 107, 114, 121]
    df = signal_frame(days, [BREACH] * 4)
    assert fires(df, threshold=THR) is True


def test_two_readings_gap_30_no_fire():
    """[100,130] gap 30 > 14 -> run restarts, NO fire.

    A span-only checker would (wrongly) fire because the run would never reach
    20 days; this asserts the gap-restart resets the run.
    """
    df = signal_frame([100, 130], [BREACH, BREACH])
    assert fires(df, threshold=THR) is False


def test_two_readings_gap_21_no_fire():
    """[100,121] gap 21 > 14 -> run restarts, NO fire.

    DISCRIMINATING: span = 121-100 = 20 >= 20, so a span-only checker FIRES.
    Correct answer is NO fire because the 21-day gap > MAX_GAP_DAYS restarts the
    run (span resets to 0). This catches a missing gap-restart.
    """
    df = signal_frame([100, 121], [BREACH, BREACH])
    assert fires(df, threshold=THR) is False


def test_break_mid_run_resets_clock():
    """An above-threshold reading mid-run breaks it and resets the clock.

    days 100..110 breach, day 111 SAFE (breaks run), days 112..120 breach.
    Neither segment spans 20 days, so NO fire. (Same data without the break
    fires — guarded by the consecutive test above.)
    """
    days = list(range(100, 121))
    vals = [BREACH] * len(days)
    vals[days.index(111)] = SAFE
    df = signal_frame(days, vals)
    assert fires(df, threshold=THR) is False

    # Sanity: identical span WITHOUT the break does fire.
    df2 = signal_frame(days, [BREACH] * len(days))
    assert fires(df2, threshold=THR) is True


# ---------------------------------------------------------------------------
# DIRECTION = "above"  (flood / heat: higher-is-worse)
# ---------------------------------------------------------------------------
def test_direction_above_fires():
    """21 consecutive daily ABOVE-threshold readings -> FIRE (proves heat/flood)."""
    hi_thr = 1.2
    days = list(range(100, 121))
    df = signal_frame(days, [1.5] * len(days))  # all >= 1.2
    assert fires(df, threshold=hi_thr, direction="above") is True


def test_direction_above_below_values_no_fire():
    """Same cadence but values BELOW the 'above' threshold -> NO fire."""
    hi_thr = 1.2
    days = list(range(100, 121))
    df = signal_frame(days, [0.0] * len(days))  # all < 1.2, never breaches
    assert fires(df, threshold=hi_thr, direction="above") is False


# ---------------------------------------------------------------------------
# Multi-sensor consensus path (no single sensor can fire)
# ---------------------------------------------------------------------------
def test_multisensor_consensus_required():
    """Two sensors over a 21-day daily run.

    One-sensor-only-below across the whole run does NOT fire (min_sensors=2);
    both-below does fire. Exercises the consensus_count comparator + trigger.
    """
    days = list(range(100, 121))
    dates = days_to_dates(days)
    # sensor_a always breaches, sensor_b never -> only 1 in breach -> no consensus
    df_one = pd.DataFrame({
        "date": dates,
        "ndvi_anomaly": [-1.5] * len(days),
        "spi3": [0.0] * len(days),
    })
    out_one = apply_consensus_trigger(
        df_one, sensors=["ndvi_anomaly", "spi3"], min_sensors=2, threshold=THR
    )
    assert bool(out_one["triggered"].any()) is False

    # both sensors breach every scene -> 2 in breach -> consensus -> FIRE
    df_two = pd.DataFrame({
        "date": dates,
        "ndvi_anomaly": [-1.5] * len(days),
        "spi3": [-1.5] * len(days),
    })
    out_two = apply_consensus_trigger(
        df_two, sensors=["ndvi_anomaly", "spi3"], min_sensors=2, threshold=THR
    )
    assert bool(out_two["triggered"].any()) is True


def test_config_object_path():
    """ConsensusConfig dataclass drives the same outcome as keyword overrides."""
    days = list(range(100, 121))
    df = signal_frame(days, [BREACH] * len(days))
    cfg = ConsensusConfig(threshold=THR, min_sensors=1, sensors=["signal"])
    out = apply_consensus_trigger(df, cfg)
    assert bool(out["triggered"].any()) is True
    assert first_trigger_date(out) is not None


def test_confirmations_counter_present():
    """The new confirmations counter is exposed and resets on a gap-restart."""
    # [100,121]: gap 21 > 14 -> second row starts a fresh run, confirmations 1.
    df = signal_frame([100, 121], [BREACH, BREACH])
    out = apply_consensus_trigger(df, sensors=["signal"], min_sensors=1, threshold=THR)
    confs = list(out["confirmations"])
    assert confs == [1, 1], confs  # both rows are run-starts, neither confirmed up


def test_confirmations_clause_is_load_bearing():
    """Isolate the NEW confirmations clause: same span, only confirmations differ.

    With persistence_days=20, max_gap_days=30 the gap-restart no longer co-forces
    >=3 scenes, so this is the ONLY pair where the confirmations AND changes the
    fire decision (every other test passes with or without the clause).

    [100,125]: gap 25 <= 30 -> run continues, span 25 >= 20, but confirmations=2
               < 3 -> NO fire. (A span-only impl would WRONGLY fire here.)
    [100,113,125]: span 25 >= 20, confirmations=3 -> FIRE.
    """
    kw = dict(sensors=["signal"], min_sensors=1, threshold=THR,
              persistence_days=20, max_gap_days=30, min_confirmations=3)

    df_no = signal_frame([100, 125], [BREACH, BREACH])
    out_no = apply_consensus_trigger(df_no, **kw)
    assert bool(out_no["triggered"].any()) is False, list(out_no["confirmations"])

    df_yes = signal_frame([100, 113, 125], [BREACH, BREACH, BREACH])
    out_yes = apply_consensus_trigger(df_yes, **kw)
    assert bool(out_yes["triggered"].any()) is True, list(out_yes["confirmations"])


def test_consensus_count_direction():
    """consensus_count applies the SAME comparator as the trigger, both ways."""
    df = pd.DataFrame({
        "date": days_to_dates([1, 2]),
        "a": [-1.5, 0.5],
        "b": [-1.0, 2.0],
    })
    below = consensus_count(df.copy(), threshold=-1.2, sensors=["a", "b"], direction="below")
    assert list(below["sensors_in_breach"]) == [1, 0]  # row0: only a<=-1.2
    above = consensus_count(df.copy(), threshold=1.2, sensors=["a", "b"], direction="above")
    assert list(above["sensors_in_breach"]) == [0, 1]  # row1: only b>=1.2


# ---------------------------------------------------------------------------
# Climatology / z-score anomaly math (offline)
# ---------------------------------------------------------------------------
def test_zscore_anomaly_math():
    """zscore_anomaly = (value - clim_mean)/clim_std vs baseline-year monthly clim."""
    # Baseline: Januarys of 2020,2021,2022 with values 10,20,30 -> mean 20, std 10.
    rows = [
        ("2020-01-15", 10.0),
        ("2021-01-15", 20.0),
        ("2022-01-15", 30.0),
        ("2023-01-15", 40.0),  # target year, not in baseline
    ]
    df = pd.DataFrame(rows, columns=["date", "level"])
    out = zscore_anomaly(df, "level", baseline_years=[2020, 2021, 2022], out_col="lvl_anom")
    target = out[out["date"] == pd.Timestamp("2023-01-15")].iloc[0]
    # mean=20, std=10 (sample/ddof=1) -> (40-20)/10 = 2.0
    assert abs(target["clim_mean"] - 20.0) < 1e-9
    assert abs(target["clim_std"] - 10.0) < 1e-9
    assert abs(target["lvl_anom"] - 2.0) < 1e-9


def test_climatology_nan_std_single_obs():
    """A baseline month with a single obs -> NaN std -> NaN anomaly (warned)."""
    df = pd.DataFrame({
        "date": ["2020-03-15", "2023-03-15"],
        "level": [5.0, 9.0],
    })
    clim = monthly_climatology(df, "level", baseline_years=[2020])
    assert pd.isna(clim.loc[3, "clim_std"])  # ddof=1 with 1 obs -> NaN
    out = zscore_anomaly(df, "level", baseline_years=[2020])
    assert out["level_anomaly"].isna().all()


def test_composite_signal_renormalizes():
    """composite_signal renormalizes over present sensors; all-NaN row -> NaN."""
    df = pd.DataFrame({
        "ndvi_anomaly": [-2.0, np.nan],
        "spi3": [np.nan, np.nan],
    })
    out = composite_signal(df, weights={"ndvi_anomaly": 1.0, "spi3": 1.0})
    assert abs(out["signal"].iloc[0] - (-2.0)) < 1e-9  # only ndvi present -> -2.0
    assert pd.isna(out["signal"].iloc[1])              # all NaN -> NaN


def _all_tests():
    g = globals()
    return [g[n] for n in sorted(g) if n.startswith("test_") and callable(g[n])]


if __name__ == "__main__":
    failures = []
    for fn in _all_tests():
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 — surface every failure
            failures.append((fn.__name__, exc))
            print(f"  FAIL  {fn.__name__}: {exc!r}")
    if failures:
        raise SystemExit(f"{len(failures)} test(s) FAILED")
    print(f"\nALL PASS ({len(_all_tests())} tests)")
