#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROFILE="${1:-${PROJECT_ROOT}/profiles/omni_trainer_dle30_15kg.yaml}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH." >&2
  exit 1
fi

python3 - "${PROFILE}" <<'PY' | bash
from omni_launcher.config import load_profile
from omni_launcher.sitl_process import build_docker_sitl_command
import shlex
import sys

profile = load_profile(sys.argv[1])
cmd, cwd = build_docker_sitl_command(
    profile,
    console=True,
    mavproxy_map=False,
    gcs_out=profile.network.gcs_out,
    wipe_params=False,
)
print("cd " + shlex.quote(str(cwd)) + " && exec " + " ".join(shlex.quote(part) for part in cmd))
PY
