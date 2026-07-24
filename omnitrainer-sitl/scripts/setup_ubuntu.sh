#!/usr/bin/env bash
set -euo pipefail

ARDUPILOT_ROOT="${OMNI_ARDUPILOT_ROOT:-${HOME}/ardupilot}"
ARDUPILOT_URL="${OMNI_ARDUPILOT_URL:-https://github.com/ArduPilot/ardupilot.git}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ "${EUID}" -eq 0 ]; then
  APT=(apt)
elif command -v sudo >/dev/null 2>&1; then
  APT=(sudo apt)
else
  echo "This installer needs root privileges for apt packages. Install sudo or run as root." >&2
  exit 1
fi

"${APT[@]}" update
"${APT[@]}" install -y \
  git \
  python3 \
  python3-pip \
  python3-venv \
  python3-setuptools \
  python3-wheel \
  python3-pyqt5 \
  python3-pyqt5.qtwebengine \
  python3-pyqt5.qtwebchannel \
  docker.io \
  docker-compose-v2 \
  rsync \
  xterm

pip_install_user() {
  if python3 -m pip install --user "$@"; then
    return 0
  fi
  echo
  echo "pip install failed. Retrying with --break-system-packages for externally managed Python environments."
  python3 -m pip install --user --break-system-packages "$@"
}

pip_install_user -r "${PROJECT_ROOT}/requirements.txt"

mkdir -p "$(dirname "${ARDUPILOT_ROOT}")"

if [ ! -d "${ARDUPILOT_ROOT}/.git" ]; then
  echo "Cloning ArduPilot into ${ARDUPILOT_ROOT}"
  git clone --recurse-submodules "${ARDUPILOT_URL}" "${ARDUPILOT_ROOT}"
else
  echo "ArduPilot checkout already exists: ${ARDUPILOT_ROOT}"
  git -C "${ARDUPILOT_ROOT}" submodule update --init --recursive
fi

if [ -x "${ARDUPILOT_ROOT}/Tools/environment_install/install-prereqs-ubuntu.sh" ]; then
  "${ARDUPILOT_ROOT}/Tools/environment_install/install-prereqs-ubuntu.sh" -y || true
fi

OMNI_MODEL_SOURCE="${PROJECT_ROOT}/assets/ardupilot/aircraft/Omni-Trainer"
OMNI_MODEL_TARGET="${ARDUPILOT_ROOT}/Tools/autotest/aircraft/Omni-Trainer"

if [ ! -d "${OMNI_MODEL_SOURCE}" ]; then
  echo "Missing bundled Omni-Trainer model source: ${OMNI_MODEL_SOURCE}"
  exit 1
fi

mkdir -p "$(dirname "${OMNI_MODEL_TARGET}")"
rsync -a "${OMNI_MODEL_SOURCE}/" "${OMNI_MODEL_TARGET}/"
echo "Installed bundled Omni-Trainer model to ${OMNI_MODEL_TARGET}"

required_files=(
  "${ARDUPILOT_ROOT}/Tools/autotest/sim_vehicle.py"
  "${ARDUPILOT_ROOT}/Tools/autotest/locations.txt"
  "${OMNI_MODEL_TARGET}/Omni-Trainer.xml"
  "${OMNI_MODEL_TARGET}/Omni-Trainer.xml"
  "${OMNI_MODEL_TARGET}/reset.xml"
  "${OMNI_MODEL_TARGET}/Engines/DLE30_EFI.xml"
  "${PROJECT_ROOT}/omnisitl.param"
  "${PROJECT_ROOT}/scripts/omni_efi_mavlink_sim.py"
  "${PROJECT_ROOT}/scripts/omni_rangefinder_mavlink_sim.py"
)

missing=0
for item in "${required_files[@]}"; do
  if [ ! -e "${item}" ]; then
    echo "Missing required launcher file: ${item}"
    missing=1
  fi
done

echo
echo "System and Python dependencies installed."
echo "Default ArduPilot root: ${ARDUPILOT_ROOT}"
echo "The profile auto-detects OMNI_ARDUPILOT_ROOT, then \$HOME/ardupilot, then legacy checkout paths."
if command -v docker >/dev/null 2>&1; then
  echo "Docker runtime is available. If Docker says permission denied, run: sudo usermod -aG docker \$USER"
  echo "Then log out and log back in before using Docker SITL."
fi

if [ "${missing}" -ne 0 ]; then
  echo
  echo "Some required files are not present."
  echo "Use an ArduPilot branch/check-out that contains Omni-Trainer, or set OMNI_ARDUPILOT_ROOT to one that does."
  exit 1
fi

echo "Setup complete. Run: python3 ${PROJECT_ROOT}/launcher.py"
