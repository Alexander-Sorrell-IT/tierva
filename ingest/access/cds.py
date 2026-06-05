"""Copernicus Climate Data Store (CDS) access — the ~/.cdsapirc bootstrap.

Promoted out of the source loaders (era5_rain, et, ccism, cgls) so the one shared
bootstrap lives in one place. CDS datasets (e.g. reanalysis-era5-land-monthly-means)
are free but require a personal access token written to `~/.cdsapirc`; the `cdsapi`
client reads that file. `setup_cdsapirc` writes it idempotently from a token.

AUTH — Copernicus CDS personal access token (a KEY, written to ~/.cdsapirc).

TRANSCRIBED FROM the working pacto-seco era5_loader / et_loader; NOT yet validated
against live data here (no network/credentials exercised).
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_CDS_URL = "https://cds.climate.copernicus.eu/api"


def setup_cdsapirc(key: str, url: str = DEFAULT_CDS_URL) -> Path:
    """Write ~/.cdsapirc from a personal access token (idempotent).

    Returns the path written. The `cdsapi.Client()` constructed inside the CDS
    loaders reads url+key from this file.
    """
    rc = Path.home() / ".cdsapirc"
    rc.write_text(f"url: {url}\nkey: {key}\n", encoding="utf-8")
    return rc
