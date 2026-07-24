#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROFILE="${1:-${PROJECT_ROOT}/profiles/omni_trainer_dle30_15kg.yaml}"
SETUP_SCRIPT="${PROJECT_ROOT}/scripts/setup_ubuntu.sh"
MAX_FIX_ATTEMPTS="${OMNI_LAUNCH_FIX_ATTEMPTS:-1}"
FIX_ATTEMPTS=0

info() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

fail() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

run_setup() {
  reason="$1"
  if [ "${FIX_ATTEMPTS}" -ge "${MAX_FIX_ATTEMPTS}" ]; then
    fail "Automatic repair already ran and requirements are still not satisfied. Last problem: ${reason}"
  fi
  if [ ! -x "${SETUP_SCRIPT}" ]; then
    fail "Setup script is missing or not executable: ${SETUP_SCRIPT}"
  fi
  if [ "${EUID}" -ne 0 ] && have_cmd sudo && ! sudo -n true >/dev/null 2>&1 && [ ! -t 0 ]; then
    fail "Automatic repair needs sudo, but this shell cannot prompt for a password. Run 'bash scripts/setup_ubuntu.sh' in a terminal, then run './launch.sh' again."
  fi
  if [ "${EUID}" -ne 0 ] && ! have_cmd sudo; then
    fail "Automatic repair needs apt privileges, but sudo is not installed. Install sudo, run the setup script as root, or install the missing requirement manually."
  fi
  FIX_ATTEMPTS=$((FIX_ATTEMPTS + 1))
  warn "Requirement problem: ${reason}"
  warn "Trying automatic repair with ${SETUP_SCRIPT}"
  "${SETUP_SCRIPT}" || fail "Automatic repair failed. Fix the error above, then run ./launch.sh again."
}

require_project_file() {
  path="$1"
  label="$2"
  [ -e "${path}" ] || fail "Missing ${label}: ${path}. Reinstall or restore this launcher repository."
}

require_local_file() {
  path="$1"
  label="$2"
  [ -e "${path}" ] || run_setup "Missing ${label}: ${path}"
}

python_import_check() {
  python3 - "$@" <<'PY'
import importlib.util
import sys

missing = [name for name in sys.argv[1:] if importlib.util.find_spec(name) is None]
if missing:
    print(", ".join(missing))
    raise SystemExit(1)
PY
}

profile_value() {
  python3 - "$PROFILE" "$1" <<'PY'
import sys
from omni_launcher.config import load_profile

profile = load_profile(sys.argv[1])
field = sys.argv[2]

if field == "ardupilot_root":
    print(profile.paths.ardupilot_root)
elif field == "model_dir":
    model = profile.aircraft.frame.split(":", 1)[-1]
    print(profile.paths.ardupilot_root / "Tools" / "autotest" / "aircraft" / model)
elif field == "model_source":
    print(profile.paths.project_root / "assets" / "ardupilot" / "aircraft" / profile.aircraft.frame.split(":", 1)[-1])
elif field == "efi_script":
    print(profile.paths.resolve_project_path(profile.paths.efi_script))
elif field == "rangefinder_script":
    print(profile.paths.resolve_project_path(profile.paths.rangefinder_script))
elif field == "param_file":
    print(profile.paths.resolve_project_path(profile.paths.param_file))
elif field == "frame":
    print(profile.aircraft.frame)
else:
    raise SystemExit(f"Unknown field: {field}")
PY
}

install_model_if_needed() {
  model_source="$1"
  model_target="$2"

  if [[ "${frame}" != jsbsim:* ]]; then
    return
  fi

  if [ ! -d "${model_source}" ]; then
    fail "Bundled Omni-Trainer model source is missing: ${model_source}"
  fi

  if [ ! -e "${model_target}/Omni-Trainer-JSBSim.xml" ] \
    || [ ! -e "${model_target}/reset.xml" ] \
    || [ ! -e "${model_target}/Engines/DLE30_EFI.xml" ]; then
    info "Installing bundled Omni-Trainer JSBSim model into ArduPilot root."
    if ! have_cmd rsync; then
      run_setup "rsync is required to install the bundled Omni-Trainer model"
    fi
    mkdir -p "$(dirname "${model_target}")" || fail "Cannot create model parent directory: $(dirname "${model_target}")"
    rsync -a "${model_source}/" "${model_target}/" || fail "Could not copy Omni-Trainer model into ${model_target}"
  fi
}

validation_summary() {
  python3 - "$PROFILE" <<'PY'
from omni_launcher.config import load_profile
from omni_launcher.validation import validate_setup
import sys

profile = load_profile(sys.argv[1])
result = validate_setup(profile, profile.engine.efi_enabled)
print(result.summary())
raise SystemExit(0 if result.ok else 1)
PY
}

preflight_once() {
  info "Checking launcher files."
  require_project_file "${PROJECT_ROOT}/launcher.py" "launcher entrypoint"
  require_project_file "${PROJECT_ROOT}/omni_launcher/config.py" "launcher package"
  require_project_file "${PROJECT_ROOT}/scripts/omni_efi_mavlink_sim.py" "EFI injector"
  require_project_file "${PROJECT_ROOT}/scripts/omni_rangefinder_mavlink_sim.py" "rangefinder injector"
  require_project_file "${PROJECT_ROOT}/omnisitl.param" "default SITL params"
  require_project_file "${PROFILE}" "launcher profile"

  info "Checking system commands."
  for cmd in git python3 xterm; do
    have_cmd "${cmd}" || run_setup "Missing command: ${cmd}"
  done

  info "Checking Python modules."
  python_import_check yaml pymavlink MAVProxy PyQt5 PyQt5.QtWebEngineWidgets PyQt5.QtWebChannel \
    || run_setup "Missing Python module(s): $(python_import_check yaml pymavlink MAVProxy PyQt5 PyQt5.QtWebEngineWidgets PyQt5.QtWebChannel 2>/dev/null || true)"

  info "Checking display environment for Qt."
  if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    fail "No DISPLAY or WAYLAND_DISPLAY is set. Start a desktop session or enable X/Wayland before launching the GUI."
  fi

  info "Reading profile."
  ardupilot_root="$(profile_value ardupilot_root)" || run_setup "Profile could not be loaded: ${PROFILE}"
  frame="$(profile_value frame)" || run_setup "Could not read aircraft frame from profile"
  model_dir="$(profile_value model_dir)" || run_setup "Could not read model directory from profile"
  model_source="$(profile_value model_source)" || run_setup "Could not read bundled model source from profile"
  efi_script="$(profile_value efi_script)" || run_setup "Could not read EFI script from profile"
  rangefinder_script="$(profile_value rangefinder_script)" || run_setup "Could not read rangefinder script from profile"
  param_file="$(profile_value param_file)" || run_setup "Could not read param file from profile"

  info "Checking ArduPilot checkout: ${ardupilot_root}"
  if [ ! -d "${ardupilot_root}/.git" ]; then
    run_setup "ArduPilot checkout is missing: ${ardupilot_root}"
  fi

  require_local_file "${ardupilot_root}/Tools/autotest/sim_vehicle.py" "ArduPilot sim_vehicle.py"

  if [[ "${frame}" == jsbsim:* ]]; then
    if ! have_cmd JSBSim && ! have_cmd jsbsim; then
      run_setup "Missing JSBSim executable"
    fi
  fi
  require_local_file "${ardupilot_root}/Tools/autotest/locations.txt" "ArduPilot locations.txt"
  require_project_file "${efi_script}" "bundled EFI script"
  require_project_file "${rangefinder_script}" "bundled rangefinder script"
  require_project_file "${param_file}" "bundled SITL param file"

  install_model_if_needed "${model_source}" "${model_dir}"

  info "Running launcher validation."
  if ! validation_output="$(validation_summary 2>&1)"; then
    warn "${validation_output}"
    run_setup "Launcher validation failed"
  fi
  printf '%s\n' "${validation_output}"
}

info "Omni Trainer SITL Launcher preflight"
info "Project root: ${PROJECT_ROOT}"
info "Profile: ${PROFILE}"

while true; do
  if preflight_once; then
    break
  fi
done

info "All requirements passed. Launching app."
exec python3 "${PROJECT_ROOT}/launcher.py" "${PROFILE}"
