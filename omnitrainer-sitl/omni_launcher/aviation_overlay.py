from __future__ import annotations

import csv
import io
import json
import math
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

OURAIRPORTS_AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OURAIRPORTS_NAVAIDS_URL = "https://davidmegginson.github.io/ourairports-data/navaids.csv"
CACHE_DIR = Path.home() / ".omni_trainer_sitl_launcher" / "aviation"
CACHE_FILE = CACHE_DIR / "ourairports_airports_navaids_overlay.json"


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def empty_overlay(lat: float, lng: float, radius_km: float, message: str) -> dict[str, Any]:
    return {
        "source": "Fallback marker",
        "center": {"lat": lat, "lng": lng, "radius_km": radius_km},
        "airports": [
            {
                "ident": "WICM",
                "iata": "TSY",
                "name": "Wiriadinata / Tasikmalaya fallback marker",
                "type": "small_airport",
                "municipality": "Tasikmalaya",
                "lat": -7.345483,
                "lng": 108.245422,
                "elevation_ft": None,
                "distance_km": haversine_km(lat, lng, -7.345483, 108.245422),
            }
        ],
        "navaids": [],
        "warnings": [
            message,
            "Airports and navaids are from OurAirports public data when available.",
            "Verify official sources before real flight.",
        ],
        "stats": {"airports_kept": 1, "navaids_kept": 0},
    }


def load_cached_overlay(max_age_days: int | None = None) -> dict[str, Any] | None:
    if not CACHE_FILE.exists():
        return None
    if max_age_days is not None:
        max_age = max_age_days * 24 * 60 * 60
        if time.time() - CACHE_FILE.stat().st_mtime > max_age:
            return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        data.setdefault("airports", [])
        data.setdefault("navaids", [])
        data.setdefault("stats", {})
        data["stats"].setdefault("airports_kept", len(data["airports"]))
        data["stats"].setdefault("navaids_kept", len(data["navaids"]))
        return data
    except (OSError, json.JSONDecodeError):
        return None


def save_cached_overlay(data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def load_initial_overlay(lat: float, lng: float, radius_km: float, max_age_days: int) -> dict[str, Any]:
    cached = load_cached_overlay(max_age_days)
    if cached:
        cached["center"] = {"lat": lat, "lng": lng, "radius_km": radius_km}
        return cached
    return empty_overlay(lat, lng, radius_km, "No fresh aviation cache loaded yet. Refresh overlay when online.")


def _download_csv_rows(url: str, timeout: int = 30) -> list[dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "OmniTrainerSITLLauncher/2.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def build_aviation_overlay(
    center_lat: float,
    center_lng: float,
    radius_km: float,
    max_age_days: int,
    force_refresh: bool = False,
    progress_callback: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    def progress(text: str) -> None:
        if progress_callback:
            progress_callback(text)

    if not force_refresh:
        cached = load_cached_overlay(max_age_days)
        if cached:
            cached["center"] = {"lat": center_lat, "lng": center_lng, "radius_km": radius_km}
            return cached

    overlay: dict[str, Any] = {
        "source": "OurAirports public CSV dataset",
        "center": {"lat": center_lat, "lng": center_lng, "radius_km": radius_km},
        "airports": [],
        "navaids": [],
        "warnings": [
            "Airports and navaids are from OurAirports public data.",
            "Verify official sources before real flight.",
        ],
    }

    try:
        progress("Downloading OurAirports airports.csv...")
        airport_rows = _download_csv_rows(OURAIRPORTS_AIRPORTS_URL)
        if should_stop and should_stop():
            return overlay

        progress("Downloading OurAirports navaids.csv...")
        navaid_rows = _download_csv_rows(OURAIRPORTS_NAVAIDS_URL)
        if should_stop and should_stop():
            return overlay

        allowed_types = {
            "large_airport",
            "medium_airport",
            "small_airport",
            "heliport",
            "seaplane_base",
            "balloonport",
            "closed",
        }
        progress("Filtering airports near operating area...")
        for row in airport_rows:
            if should_stop and should_stop():
                return overlay
            lat = safe_float(row.get("latitude_deg"))
            lng = safe_float(row.get("longitude_deg"))
            if lat is None or lng is None:
                continue
            distance_km = haversine_km(center_lat, center_lng, lat, lng)
            if distance_km > radius_km or row.get("type", "") not in allowed_types:
                continue
            overlay["airports"].append(
                {
                    "ident": row.get("ident", ""),
                    "iata": row.get("iata_code", ""),
                    "name": row.get("name", ""),
                    "type": row.get("type", ""),
                    "municipality": row.get("municipality", ""),
                    "lat": lat,
                    "lng": lng,
                    "elevation_ft": safe_float(row.get("elevation_ft")),
                    "distance_km": distance_km,
                }
            )

        progress("Filtering navaids near operating area...")
        for row in navaid_rows:
            if should_stop and should_stop():
                return overlay
            lat = safe_float(row.get("latitude_deg"))
            lng = safe_float(row.get("longitude_deg"))
            if lat is None or lng is None:
                continue
            distance_km = haversine_km(center_lat, center_lng, lat, lng)
            if distance_km > radius_km:
                continue
            overlay["navaids"].append(
                {
                    "ident": row.get("ident", ""),
                    "name": row.get("name", ""),
                    "type": row.get("type", ""),
                    "frequency_khz": row.get("frequency_khz", ""),
                    "lat": lat,
                    "lng": lng,
                    "elevation_ft": safe_float(row.get("elevation_ft")),
                    "distance_km": distance_km,
                }
            )

        overlay["airports"].sort(key=lambda item: item.get("distance_km", 999999.0))
        overlay["navaids"].sort(key=lambda item: item.get("distance_km", 999999.0))
        overlay["stats"] = {
            "airports_kept": len(overlay["airports"]),
            "navaids_kept": len(overlay["navaids"]),
        }
        save_cached_overlay(overlay)
        progress(f"Aviation overlay updated: {len(overlay['airports'])} airports, {len(overlay['navaids'])} navaids.")
        return overlay
    except Exception as exc:
        cached = load_cached_overlay(None)
        if cached:
            cached["center"] = {"lat": center_lat, "lng": center_lng, "radius_km": radius_km}
            cached.setdefault("warnings", []).append(f"Refresh failed; using cached overlay. Error: {exc}")
            return cached
        return empty_overlay(center_lat, center_lng, radius_km, f"No internet/cache for aviation overlay. Error: {exc}")
