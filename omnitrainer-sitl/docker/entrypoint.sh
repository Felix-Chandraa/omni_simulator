#!/usr/bin/env bash
set -euo pipefail

ARDUPILOT_ROOT="${ARDUPILOT_ROOT:-/opt/ardupilot}"
OMNI_WORKSPACE="${OMNI_WORKSPACE:-/workspace/omnitrainer-sitl}"
MODEL_SOURCE="${OMNI_WORKSPACE}/assets/ardupilot/aircraft/Omni-Trainer"
MODEL_TARGET="${ARDUPILOT_ROOT}/Tools/autotest/aircraft/Omni-Trainer"
LOCATIONS_FILE="${ARDUPILOT_ROOT}/Tools/autotest/locations.txt"

if [ -d "${MODEL_SOURCE}" ]; then
  mkdir -p "$(dirname "${MODEL_TARGET}")"
  rsync -a --delete "${MODEL_SOURCE}/" "${MODEL_TARGET}/"
fi

if [ -n "${OMNI_LOCATION_NAME:-}" ]; then
  python3 - "${LOCATIONS_FILE}" <<'PY'
from pathlib import Path
import os
import sys

path = Path(sys.argv[1])
name = os.environ["OMNI_LOCATION_NAME"]
lat = float(os.environ["OMNI_LOCATION_LAT"])
lng = float(os.environ["OMNI_LOCATION_LNG"])
alt = float(os.environ["OMNI_LOCATION_ALT_MSL"])
heading = float(os.environ["OMNI_LOCATION_HEADING"])
new_line = f"{name}={lat:.7f},{lng:.7f},{alt:.2f},{heading:.1f}"
prefix = f"{name}="

lines = path.read_text().splitlines(True) if path.exists() else []
out = []
replaced = False
for line in lines:
    if line.startswith(prefix):
        out.append(new_line + "\n")
        replaced = True
    else:
        out.append(line)
if not replaced:
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    out.append(new_line + "\n")
path.write_text("".join(out))
print(f"Wrote Docker SITL location: {new_line}")
PY
fi

cd "${ARDUPILOT_ROOT}"
exec "$@"
