#!/usr/bin/env bash
# run_demo.sh — jalankan SITL Omni-Trainer.
#
#   ./run_demo.sh              -> backend JSBSim, model Omni-Trainer
#   ./run_demo.sh plane        -> backend fisika bawaan ArduPilot
#   ./run_demo.sh jsbsim -w    -> wipe eeprom; parm default otomatis dimuat ulang
#
# Argumen setelah MODE diteruskan apa adanya ke sim_vehicle.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AP_DIR="${ROOT}/omnitrainer-sitl/ardupilot"
VENV="${ROOT}/.venv"

[ -d "${AP_DIR}/Tools/autotest" ] || { echo "ardupilot belum ada — jalankan ./setup.sh dulu" >&2; exit 1; }
[ -d "${VENV}" ] || { echo "venv belum ada — jalankan ./setup.sh dulu" >&2; exit 1; }

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

MODE="${1:-jsbsim}"
[ $# -gt 0 ] && shift

# 1) Parm default Omni-Trainer: diterapkan otomatis saat eeprom dibuat baru
#    (instalasi segar / flag -w). Tanpa ini, boot pertama memakai default
#    ArduPlane polos — sumber bug "pesawat jalan sendiri sebelum arming".
OMNI_PARM="${AP_DIR}/Tools/autotest/aircraft/Omni-Trainer/omni_trainer_sitl.parm"
ARGS=( -v ArduPlane -L Wiriadinata )
if [ "${MODE}" = "plane" ]; then
    ARGS+=( -f plane )
else
    ARGS+=( -f jsbsim:Omni-Trainer --enable-fgview )
fi
if [ -f "${OMNI_PARM}" ]; then
    ARGS+=( "--add-param-file=${OMNI_PARM}" )
    if [ "${MODE}" = "plane" ]; then
        echo "[run_demo] CATATAN: backend 'plane' memakai tuning Omni-Trainer" >&2
        echo "           (termasuk RC2/RC4/SERVO2/SERVO4_REVERSED utk konvensi" >&2
        echo "           tanda JSBSim) -> kontrol pitch/yaw bisa terasa terbalik." >&2
        echo "           Mode ini hanya utk pembanding kasar, bukan tuning nyata." >&2
    fi
else
    echo "[run_demo] PERINGATAN: ${OMNI_PARM} tidak ada — jalankan omnitrainer-sitl/install.sh" >&2
fi

# 2) Misi default (takeoff Wiriadinata): loader latar belakang yang menunggu
#    heartbeat lalu upload HANYA bila autopilot belum punya misi. Idempoten;
#    log di /tmp/omni_mission_load.log. Wajib agar mode AUTO bisa takeoff.
MISSION="${ROOT}/omnitrainer-sitl/assets/missions/wiriadinata_default.txt"
LOADER="${ROOT}/omnitrainer-sitl/scripts/load_default_mission.py"
LOADER_PID=""
if [ -f "${MISSION}" ] && [ -f "${LOADER}" ]; then
    # Interpreter venv eksplisit (pymavlink ada di sana), bukan python3 PATH.
    PY="${VENV}/bin/python3"
    [ -x "${PY}" ] || PY="python3"
    "${PY}" "${LOADER}" --mission "${MISSION}" > /tmp/omni_mission_load.log 2>&1 &
    LOADER_PID=$!
fi

# Bersih-bersih saat keluar (Ctrl+C / exit MAVProxy). Tanpa ini, loader misi
# atau binary SITL bisa jadi proses yatim yang menahan port 5760/5762/14550,
# lalu bikin run berikutnya gagal dgn error yang membingungkan.
CLEANED=0
cleanup() {
    [ "${CLEANED}" = "1" ] && return 0   # trap INT + EXIT bisa keduanya memicu
    CLEANED=1
    if [ -n "${LOADER_PID}" ] && kill -0 "${LOADER_PID}" 2>/dev/null; then
        kill "${LOADER_PID}" 2>/dev/null || true
    fi
    # Lingkup sempit: HANYA proses yang dijalankan dari pohon ardupilot proyek
    # ini (arduplane SITL, JSBSim). Aman terhadap editor/terminal yang kebetulan
    # memuat kata "ArduPlane" di baris perintahnya.
    if pgrep -f "${AP_DIR}" >/dev/null 2>&1; then
        echo "[run_demo] membersihkan proses SITL yang tersisa..." >&2
        pkill -f "${AP_DIR}" 2>/dev/null || true
    fi
    return 0
}
trap cleanup EXIT INT TERM

cd "${AP_DIR}"
# set -e aktif: pakai '|| STATUS=$?' agar exit code tetap tertangkap saat
# sim_vehicle keluar tidak nol (mis. ditutup Ctrl+C).
STATUS=0
./Tools/autotest/sim_vehicle.py "${ARGS[@]}" "$@" || STATUS=$?
cleanup
exit "${STATUS}"
