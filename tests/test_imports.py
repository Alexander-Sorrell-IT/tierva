"""Smoke test (TEST_PLAN rung S) — zero network, zero credentials.

The 8 loaders were transcribed from pacto-seco and re-pointed at the new
`ingest/access/*` shared patterns (`from ..access.planetary_computer import
search`, etc.). A single broken relative import or a renamed symbol fails
SILENTLY until a live pull — so this is the cheapest, fastest CI gate: it just
imports every loader + the access layer + the kernel and asserts they load with
no traceback. No network, no auth, no data is touched.

Run with a venv that has the geo deps (pandas/numpy/rioxarray/odc.stac/rasterio),
e.g. the Pacto Seco venv:
  /Users/.../pacto-seco/.venv/bin/python \
      /Users/.../tierva/tests/test_imports.py

Pass = 8x "OK <loader>" + the access/kernel line, no "FAIL", no traceback.
Bare-loop style (no pytest needed), matching test_consensus.py.
"""
from __future__ import annotations

import importlib
import os
import sys

# Make the ingest + kernel packages importable when run as a bare script,
# regardless of the current working directory.
TIERVA = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TIERVA not in sys.path:
    sys.path.insert(0, TIERVA)

# The 8 transcribed loaders (TEST_PLAN rung S / L matrix).
LOADER_MODULES = [
    "ingest.sources.sentinel2",
    "ingest.sources.sentinel1_sar",
    "ingest.sources.worldcover_cropland",
    "ingest.sources.modis_ndvi",
    "ingest.sources.modis_lst",
    "ingest.sources.smap",
    "ingest.sources.chirps",
    "ingest.sources.era5_rain",
]

# Shared access layer + the domain-agnostic kernel.
ACCESS_KERNEL_MODULES = [
    "ingest.access.planetary_computer",
    "ingest.access.earthdata",
    "ingest.access.cds",
    "kernel.consensus",
    "kernel.climatology",
]

# The public entrypoint each loader is supposed to expose (a renamed/missing
# symbol is exactly the silent break this smoke test exists to catch).
LOADER_ENTRYPOINTS = {
    "ingest.sources.sentinel2": "ndvi_timeseries",
    "ingest.sources.sentinel1_sar": "sar_timeseries",
    "ingest.sources.worldcover_cropland": "cropland_mask",
    "ingest.sources.modis_ndvi": "modis_ndvi_timeseries",
    "ingest.sources.modis_lst": "lst_timeseries",
    "ingest.sources.smap": "smap_timeseries",
    "ingest.sources.chirps": "chirps_timeseries",
    "ingest.sources.era5_rain": "precip_monthly",
}


def test_loaders_import():
    """Every loader imports with no traceback (the core refactor guard)."""
    for mod in LOADER_MODULES:
        m = importlib.import_module(mod)
        print(f"  OK  {mod}")
        assert m is not None


def test_access_and_kernel_import():
    """The shared access layer + kernel import (one combined assertion)."""
    for mod in ACCESS_KERNEL_MODULES:
        m = importlib.import_module(mod)
        assert m is not None
    print("  OK  access+kernel import")


def test_loader_entrypoints_present():
    """Each loader still exposes its documented public entrypoint.

    Catches a renamed/deleted symbol that a bare import would miss (the module
    loads, but a caller's `from x import y` would break at runtime)."""
    for mod, fn in LOADER_ENTRYPOINTS.items():
        m = importlib.import_module(mod)
        assert hasattr(m, fn), f"{mod} is missing its entrypoint {fn!r}"
        assert callable(getattr(m, fn)), f"{mod}.{fn} is not callable"
    print("  OK  loader entrypoints present")


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
