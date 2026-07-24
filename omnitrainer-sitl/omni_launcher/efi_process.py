from __future__ import annotations

from pathlib import Path

from .config import LauncherProfile
from .process_utils import python_executable


def build_efi_command(
    profile: LauncherProfile,
    connect: str,
    gcs_out: str,
    rate_hz: int,
    print_rate_hz: int,
) -> tuple[list[str], Path]:
    script = profile.paths.resolve_project_path(profile.paths.efi_script)
    shell_cmd = (
        f"'{python_executable()}' '{script}' "
        f"--connect '{connect.strip()}' "
        f"--rate {int(rate_hz)} "
        f"--print-rate {int(print_rate_hz)}"
    )
    if profile.efi.force_running:
        shell_cmd += " --force-running"
    if profile.efi.simulate_egt:
        shell_cmd += " --simulate-egt"
    if profile.efi.simulate_fuel_flow:
        shell_cmd += " --simulate-fuel-flow"
    if profile.efi.rng_inject:
        shell_cmd += f" --rng-inject --rng-rate {int(profile.rangefinder.rate_hz)} --rng-min-cm {profile.rangefinder.min_cm} --rng-max-cm {profile.rangefinder.max_cm} --rng-id {profile.rangefinder.sensor_id}"
    if gcs_out.strip():
        shell_cmd += f" --gcs-out '{gcs_out.strip()}'"
    else:
        shell_cmd += " --gcs-out ''"
    return ["bash", "-lc", shell_cmd], profile.paths.project_root
