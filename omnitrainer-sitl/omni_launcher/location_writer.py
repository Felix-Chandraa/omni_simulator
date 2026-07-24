from __future__ import annotations

from pathlib import Path


def locations_file_for_ardupilot(ardupilot_root: Path) -> Path:
    return ardupilot_root / "Tools" / "autotest" / "locations.txt"


def format_location_line(name: str, lat: float, lng: float, alt_msl_m: float, heading_deg: float) -> str:
    return f"{name}={lat:.7f},{lng:.7f},{alt_msl_m:.2f},{heading_deg:.1f}"


def write_location(
    ardupilot_root: Path,
    name: str,
    lat: float,
    lng: float,
    alt_msl_m: float,
    heading_deg: float,
) -> str:
    locations_file = locations_file_for_ardupilot(ardupilot_root)
    if not locations_file.exists():
        raise FileNotFoundError(f"locations.txt not found: {locations_file}")

    new_line = format_location_line(name, lat, lng, alt_msl_m, heading_deg)
    lines = locations_file.read_text().splitlines(True)
    output: list[str] = []
    replaced = False
    prefix = f"{name}="

    for line in lines:
        if line.startswith(prefix):
            output.append(new_line + "\n")
            replaced = True
        else:
            output.append(line)

    if not replaced:
        if output and not output[-1].endswith("\n"):
            output[-1] += "\n"
        output.append(new_line + "\n")

    locations_file.write_text("".join(output))
    return new_line
