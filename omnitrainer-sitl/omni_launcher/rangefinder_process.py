from __future__ import annotations

from pathlib import Path

from .config import LauncherProfile
from .process_utils import python_executable


def build_rangefinder_command(
    profile: LauncherProfile,
    connect: str,
    gcs_out: str,
    rate_hz: int,
    print_rate_hz: int,
    min_cm: int,
    max_cm: int,
    sensor_id: int,
) -> tuple[list[str], Path]:
    script = profile.paths.resolve_project_path(profile.paths.rangefinder_script)
    shell_cmd = (
        f"'{python_executable()}' '{script}' "
        f"--connect '{connect.strip()}' "
        f"--rate {int(rate_hz)} "
        f"--print-rate {int(print_rate_hz)} "
        f"--min-cm {int(min_cm)} "
        f"--max-cm {int(max_cm)} "
        f"--sensor-id {int(sensor_id)}"
    )
    if gcs_out.strip():
        shell_cmd += f" --gcs-out '{gcs_out.strip()}'"
    else:
        shell_cmd += " --gcs-out ''"
    return ["bash", "-lc", shell_cmd], profile.paths.project_root
