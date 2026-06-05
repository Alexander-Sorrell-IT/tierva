"""NASA Earthdata access — the CMR-search + bearer-token download pattern.

Promoted out of the source loaders (smap, grace) so the one shared pattern lives
in one place. The split of responsibilities:

  * CMR collection/granule SEARCH is PUBLIC (no token needed). `cmr_search`
    returns the raw granule `entry` dicts; each loader picks the data link(s) it
    wants (smap: paginate + one-per-day .h5; grace: the single full-record .nc).
  * Granule DATA DOWNLOAD is auth-gated. `download` sets an
    `Authorization: Bearer <token>` header (the same header earthaccess would
    set), follows the 303 → signed-CloudFront redirect, and raises
    `EarthdataAuthError` on HTTP 401/403 rather than silently writing a partial
    file or returning empty/NaN.

AUTH — NASA Earthdata bearer token (NO password)
================================================
Read a bearer JWT from the `EARTHDATA_TOKEN` env var, else from `~/.edl_token`.
No username/password flow. If the token is missing/expired/rejected the loaders
surface a clear `EarthdataAuthError` naming the failure.

TRANSCRIBED FROM the working pacto-seco smap_loader / grace_loader; NOT yet
validated against live data here (no network/credentials exercised).
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"
TOKEN_PATH = Path.home() / ".edl_token"


class EarthdataAuthError(RuntimeError):
    """Raised when the Earthdata bearer token is missing/expired/rejected.

    (Unifies the former per-loader SmapAuthError / GraceAuthError.)
    """


def read_token() -> str:
    """Bearer token from EARTHDATA_TOKEN env var, else ~/.edl_token. No password."""
    tok = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not tok and TOKEN_PATH.exists():
        tok = TOKEN_PATH.read_text().strip()
    if not tok:
        raise EarthdataAuthError(
            "No Earthdata bearer token found (set EARTHDATA_TOKEN or write ~/.edl_token)."
        )
    return tok


def cmr_search(params: dict, timeout: int = 60) -> list[dict]:
    """One public CMR granule-search request (no auth). Returns the list of
    `feed.entry` dicts. Pagination / link selection is left to the caller, since
    the loaders differ (smap paginates by solar day; grace has one granule)."""
    r = requests.get(CMR_GRANULES, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json().get("feed", {}).get("entry", [])


def download(url: str, token: str, dest: Path, timeout: int = 300) -> None:
    """Bearer-auth download of one granule to `dest` (atomic via a .part rename).

    Follows the 303 → signed-CloudFront redirect (allow_redirects=True). Raises
    EarthdataAuthError on HTTP 401/403 (token missing/expired/invalid)."""
    with requests.get(
        url, headers={"Authorization": f"Bearer {token}"},
        stream=True, timeout=timeout, allow_redirects=True,
    ) as r:
        if r.status_code in (401, 403):
            raise EarthdataAuthError(
                f"Earthdata rejected the bearer token (HTTP {r.status_code}: "
                f"{r.text[:120]!r}) downloading {url}. Token missing/expired/invalid."
            )
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)
