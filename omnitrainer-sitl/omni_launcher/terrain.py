from __future__ import annotations

import json
import urllib.request


def fetch_terrain_altitude_m(lat: float, lng: float, timeout: int = 8) -> float:
    url = f"https://api.opentopodata.org/v1/srtm30m?locations={lat:.7f},{lng:.7f}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("status") not in ("OK", "ok"):
        raise RuntimeError(str(data))
    results = data.get("results") or []
    if not results:
        raise RuntimeError("No elevation result returned.")
    elevation = results[0].get("elevation")
    if elevation is None:
        raise RuntimeError("Elevation is null for this point.")
    return float(elevation)
