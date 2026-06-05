"""Tierva — "see your land" API (M0 / L1).

GET /api/parcel?lat=..&lon=..  ->  the latest parcel-true satellite readout for
ANY parcel on Earth (NDVI, radar dB, cropland), live + no-auth via the
ingest/parcel.py engine. The front-end (web/index.html) is a map: drop a pin or
search a place, see what the satellites know about that land.

Run from the repo root:
    uvicorn app.server:app --port 8077
"""
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse

from ingest.parcel import parcel_readout

app = FastAPI(title="Tierva — see your land")
WEB = Path(__file__).parent / "web"

# The load-bearing honesty boundary: only these 10 m layers resolve a single
# parcel. Coarser region-context layers (soil moisture, rainfall, groundwater)
# are deliberately NOT served at parcel zoom — that boundary is also the paid upsell.
PARCEL_TRUE = ["ndvi", "vv_db", "vh_db", "cropland", "dominant_landcover"]

WORLDCOVER = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare / sparse vegetation", 70: "Snow & ice",
    80: "Permanent water", 90: "Herbaceous wetland", 95: "Mangrove",
    100: "Moss & lichen",
}


@app.get("/api/parcel")
def api_parcel(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    buffer_m: float = Query(250, ge=50, le=2000),
):
    """Live parcel-true readout for (lat, lon). Real Copernicus/NASA data, no auth."""
    try:
        r = parcel_readout(lat, lon, buffer_m=buffer_m)
    except Exception as e:  # surface the real error rather than a 500 wall
        return JSONResponse(status_code=502, content={"error": str(e), "lat": lat, "lon": lon})
    d = r.to_dict()
    d["landcover_label"] = (
        WORLDCOVER.get(r.dominant_landcover) if r.dominant_landcover is not None else None
    )
    d["honesty"] = {
        "parcel_true_10m": PARCEL_TRUE,
        "note": "These layers resolve a single ~parcel (10 m). Soil-moisture / rainfall / "
                "groundwater are region-only and not shown at parcel zoom.",
    }
    return d


@app.get("/")
def root():
    return FileResponse(WEB / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}
