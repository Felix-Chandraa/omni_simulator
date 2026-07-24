#!/usr/bin/env bash
# setup.sh — Setup environment Omni-Trainer SITL + Feather Flight GCS
# Dijalankan sekali di mesin baru. Idempoten: aman dijalankan ulang.
#
# Yang dilakukan:
#   1. Install paket sistem dasar (git, python3-venv, build tools)
#   2. Clone ardupilot (kalau belum ada di omnitrainer-sitl/ardupilot)
#   3. Pasang aset Omni-Trainer ke pohon ardupilot (via install.sh)
#   4. Buat virtualenv .venv + install semua deps Python (termasuk JSBSim)
#   5. Daftarkan lokasi Wiriadinata ke locations.txt user
#
# Usage:
#   ./setup.sh            # setup lengkap (jsbsim + backend plane)
#   ./setup.sh --no-clone # skip clone ardupilot (kalau sudah disediakan)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITL_DIR="${ROOT}/omnitrainer-sitl"
AP_DIR="${SITL_DIR}/ardupilot"
VENV="${ROOT}/.venv"
NO_CLONE=0
[ "${1:-}" = "--no-clone" ] && NO_CLONE=1

log() { echo -e "\033[1;32m[setup]\033[0m $*"; }
warn() { echo -e "\033[1;33m[setup]\033[0m $*" >&2; }

# ---------------------------------------------------------------- 1. apt deps
if command -v apt-get >/dev/null 2>&1; then
    log "Install paket sistem (butuh sudo, sekali saja)..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        git python3 python3-venv python3-pip python3-dev \
        build-essential ccache g++ gawk \
        libxml2-dev libxslt1-dev \
        libgl1 libegl1 libxkbcommon0 libdbus-1-3 libnss3 libasound2t64 2>/dev/null \
    || sudo apt-get install -y -qq \
        git python3 python3-venv python3-pip python3-dev \
        build-essential ccache g++ gawk \
        libxml2-dev libxslt1-dev \
        libgl1 libegl1 libxkbcommon0 libdbus-1-3 libnss3 libasound2
else
    warn "apt-get tidak ditemukan — pastikan git, python3-venv, dan build tools sudah terpasang."
fi

# ------------------------------------------------------------ 2. ardupilot
if [ -d "${AP_DIR}/Tools/autotest" ]; then
    log "ardupilot sudah ada: ${AP_DIR}"
elif [ "$NO_CLONE" = "1" ]; then
    warn "ardupilot belum ada dan --no-clone dipakai. Taruh repo di ${AP_DIR} lalu jalankan ulang."
    exit 1
else
    log "Clone ardupilot (agak lama, ~beberapa menit)..."
    git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "${AP_DIR}"
fi

# Pastikan submodule lengkap (kalau repo dicopy manual tanpa submodule)
if [ -d "${AP_DIR}/.git" ]; then
    git -C "${AP_DIR}" submodule update --init --recursive --quiet || \
        warn "submodule update gagal — lanjut, build mungkin akan komplain."
fi

# ------------------------------------------- 3. aset Omni-Trainer -> ardupilot
log "Pasang aset Omni-Trainer ke pohon ardupilot..."
OMNI_ARDUPILOT_ROOT="${AP_DIR}" bash "${SITL_DIR}/install.sh"

# ---------------------------------------------------------------- 4. venv
if [ ! -d "${VENV}" ]; then
    log "Buat virtualenv di ${VENV}..."
    python3 -m venv "${VENV}"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
log "Install deps Python ke venv..."
pip install --quiet --upgrade pip wheel setuptools
# Deps GCS (Feather Flight)
pip install --quiet -r "${ROOT}/Feather-Flight-main/requirements.txt"
# Deps sim_vehicle.py / build SITL
pip install --quiet "empy==3.3.4" pexpect future intelhex pyserial MAVProxy
# JSBSim: wheel pip sudah menyertakan binary JSBSim di .venv/bin
pip install --quiet jsbsim || warn "pip install jsbsim gagal — backend jsbsim tidak akan jalan, pakai backend plane saja."

if command -v JSBSim >/dev/null 2>&1; then
    log "JSBSim binary OK: $(command -v JSBSim)"
else
    warn "Binary JSBSim tidak ketemu di PATH venv. Demo tetap bisa pakai backend 'plane'."
fi

# ---------------------------------------------- 5. lokasi Wiriadinata (user)
LOC_DIR="${HOME}/.config/ardupilot"
LOC_FILE="${LOC_DIR}/locations.txt"
mkdir -p "${LOC_DIR}"
touch "${LOC_FILE}"
if grep -qi '^Wiriadinata=' "${LOC_FILE}"; then
    log "Lokasi Wiriadinata sudah terdaftar."
else
    echo "Wiriadinata=-7.346914,108.2463725,349.0,327.66" >> "${LOC_FILE}"
    log "Lokasi Wiriadinata ditambahkan ke ${LOC_FILE}"
fi

log "Selesai. Cara pakai:"
echo ""
echo "    source .venv/bin/activate"
echo "    ./run_demo.sh            # backend jsbsim (model Omni-Trainer)"
echo "    ./run_demo.sh plane      # backend bawaan ArduPilot (paling gampang buat demo)"
echo ""
echo "  Build SITL pertama kali otomatis dilakukan sim_vehicle.py (agak lama)."
