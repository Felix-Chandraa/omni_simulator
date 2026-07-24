#!/usr/bin/env python3
"""P5 — Generator konfigurasi lokasi (SDD Bab 8 langkah 3-5).

Membaca SATU file sumber `locations/<name>.env` lalu MENYEBAR-nya (bukan
menebak) ke semua konsumen:
  1. baris ArduPilot `NAME=LAT,LON,ALT,HDG` (opsional --write-ardupilot ->
     $HOME/.config/ardupilot/locations.txt, file USER, tahan `git pull`);
  2. `locations/active_location.json` (dibaca frontend `location.js`);
  3. cetak blok `config.js home{}` + `views.ground.gcs{}` (utk paste manual
     bila tidak pakai active_location.json);
  4. cetak blok `start_location` YAML profil SITL.

Turunan yang dihitung (bukan diketik ulang):
  - HDG_TRUE dari dua ujung runway bila RWY15/RWY33 diisi (SDD langkah 1):
      heading = atan2(dLon*cos(mean_lat), dLat), threshold 15 = ujung NW.
  - GEOID_OFFSET_M = CESIUM_TERRAIN_M - SITL_MSL_M (SDD langkah 2, utk P1).

Pemakaian:
  python3 tools/gen_location_config.py locations/wiriadinata.env
  python3 tools/gen_location_config.py locations/wiriadinata.env --write-ardupilot
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path


def parse_env(path: Path) -> dict:
    data: dict = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        # buang komentar inline pada nilai (mis. ALT_M=349.0  # ukur)
        val = val.split("#", 1)[0].strip()
        data[key.strip()] = val
    return data


def _f(data: dict, key: str):
    v = data.get(key, "")
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def heading_from_ends(lat15, lon15, lat33, lon33) -> float:
    """Heading true (deg, 0..360) threshold15 -> threshold33 (SDD langkah 1)."""
    mean_lat = math.radians((lat15 + lat33) / 2.0)
    d_lat = lat33 - lat15
    d_lon = (lon33 - lon15) * math.cos(mean_lat)
    hdg = math.degrees(math.atan2(d_lon, d_lat))
    return (hdg + 360.0) % 360.0


def resolve(data: dict) -> dict:
    name = data.get("NAME", "Location")
    lat = _f(data, "LAT")
    lon = _f(data, "LON")
    alt = _f(data, "ALT_M")
    hdg = _f(data, "HDG_TRUE")

    # HDG dari ujung runway bila tersedia (menimpa HDG_TRUE).
    ends = [_f(data, k) for k in ("RWY15_LAT", "RWY15_LON", "RWY33_LAT", "RWY33_LON")]
    if all(e is not None for e in ends):
        hdg = round(heading_from_ends(*ends), 2)

    geoid = None
    cesium_h = _f(data, "CESIUM_TERRAIN_M")
    sitl_h = _f(data, "SITL_MSL_M")
    if cesium_h is not None and sitl_h is not None:
        geoid = round(cesium_h - sitl_h, 3)

    if None in (lat, lon, alt, hdg):
        missing = [k for k, v in (("LAT", lat), ("LON", lon), ("ALT_M", alt), ("HDG_TRUE", hdg)) if v is None]
        raise SystemExit(f"[gen] nilai wajib kosong: {', '.join(missing)} — isi .env dulu.")

    return {
        "name": name,
        "lat": lat,
        "lon": lon,
        "altMsl": alt,
        "headingTrue": hdg,
        "gcs": {
            "lat": _f(data, "GCS_LAT"),
            "lon": _f(data, "GCS_LON"),
            "altMsl": _f(data, "GCS_ALT_M"),
        },
        "geoidOffsetM": geoid,  # None sampai diukur (P5 langkah 2)
    }


def ardupilot_line(loc: dict) -> str:
    return (f"{loc['name']}={loc['lat']:.7f},{loc['lon']:.7f},"
            f"{loc['altMsl']:.2f},{loc['headingTrue']:.1f}")


def write_ardupilot_user(loc: dict) -> Path:
    """Tulis/replace baris di $HOME/.config/ardupilot/locations.txt (buat bila belum ada)."""
    path = Path(os.path.expanduser("~/.config/ardupilot/locations.txt"))
    path.parent.mkdir(parents=True, exist_ok=True)
    line = ardupilot_line(loc)
    prefix = f"{loc['name']}="
    lines = path.read_text().splitlines(True) if path.exists() else []
    out, replaced = [], False
    for ln in lines:
        if ln.startswith(prefix):
            out.append(line + "\n")
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append(line + "\n")
    path.write_text("".join(out))
    return path


def config_js_snippet(loc: dict) -> str:
    g = loc["gcs"]
    return (
        "// --- P5: generated dari locations/*.env (jangan edit tangan) ---\n"
        "home: {\n"
        f"  lat: {loc['lat']},\n  lon: {loc['lon']},\n  alt: {loc['altMsl']}\n"
        "},\n"
        "// views.ground.gcs:\n"
        f"gcs: {{ lat: {g['lat']}, lon: {g['lon']}, altMsl: {g['altMsl']} }}"
    )


def yaml_start_location(loc: dict) -> str:
    return (
        "start_location:\n"
        f"  name: {loc['name']}\n"
        f"  lat: {loc['lat']}\n"
        f"  lng: {loc['lon']}\n"
        f"  alt_msl_m: {loc['altMsl']}\n"
        f"  heading_deg: {loc['headingTrue']}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Sebar file lokasi tunggal ke semua konsumen.")
    ap.add_argument("env", type=Path, help="path ke locations/<name>.env")
    ap.add_argument("--write-ardupilot", action="store_true",
                    help="tulis baris ke ~/.config/ardupilot/locations.txt (file user)")
    ap.add_argument("--json-out", type=Path, default=None,
                    help="path active_location.json (default: di samping .env)")
    args = ap.parse_args()

    if not args.env.exists():
        raise SystemExit(f"[gen] tidak ada: {args.env}")

    loc = resolve(parse_env(args.env))

    json_out = args.json_out or (args.env.parent / "active_location.json")
    json_out.write_text(json.dumps(loc, indent=2))

    print(f"[gen] lokasi: {loc['name']}  spawn=({loc['lat']},{loc['lon']}) "
          f"alt={loc['altMsl']}m hdg={loc['headingTrue']}°")
    if loc["geoidOffsetM"] is None:
        print("[gen] GEOID_OFFSET_M: BELUM diukur (isi CESIUM_TERRAIN_M & SITL_MSL_M di .env).")
    else:
        print(f"[gen] GEOID_OFFSET_M = {loc['geoidOffsetM']} m (dipakai P1 advisory).")
    print(f"[gen] active_location.json -> {json_out}")
    print("\n# --- ArduPilot locations.txt ---")
    print(ardupilot_line(loc))
    if args.write_ardupilot:
        p = write_ardupilot_user(loc)
        print(f"[gen] ditulis ke {p}")
    print("\n# --- paste ke src/js/config.js (bila tak pakai active_location.json) ---")
    print(config_js_snippet(loc))
    print("\n# --- blok profil SITL (profiles/*.yaml) ---")
    print(yaml_start_location(loc))


if __name__ == "__main__":
    main()