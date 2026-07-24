#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-${OMNI_ARDUPILOT_ROOT:-${HOME}/ardupilot}/Tools/autotest/aircraft}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$TARGET"
rm -rf "$TARGET/Omni-Trainer"
cp -a "$SCRIPT_DIR" "$TARGET/Omni-Trainer"
echo "Installed Omni-Trainer to $TARGET/Omni-Trainer"
echo "Run: cd \"$(cd "${TARGET}/../../.." && pwd)\" && ./Tools/autotest/sim_vehicle.py -v ArduPlane -f jsbsim:Omni-Trainer --console --map"
