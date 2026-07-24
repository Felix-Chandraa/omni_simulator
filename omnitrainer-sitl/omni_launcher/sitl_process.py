from __future__ import annotations

import shlex
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, pyqtSignal

from .config import LauncherProfile


DOCKER_IMAGE = "omnitrainer-sitl:local"
DOCKER_CONTAINER = "omnitrainer-sitl"

# QGC berjalan di host dan listen UDP 14551.
# Container mengirim MAVLink keluar ke gateway docker0 host.
# Jangan publish/bind UDP port 14551 di docker run, karena port itu dipakai QGC.
DOCKER_GCS_OUT = "udpout:172.17.0.1:14551"


class ProcessRunner(QObject):
    output = pyqtSignal(str)
    started = pyqtSignal(str)
    finished = pyqtSignal(str, int)
    failed_to_start = pyqtSignal(str)

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.proc: QProcess | None = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def start(self, cmd: list[str], cwd: Path | None = None) -> bool:
        if self.is_running():
            self.output.emit(f"[{self.name}] already running.")
            return False

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)

        if cwd:
            self.proc.setWorkingDirectory(str(cwd))

        self.proc.readyReadStandardOutput.connect(self._read_output)
        self.proc.started.connect(lambda: self.started.emit(self.name))
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(self._error)

        self.output.emit(f"[{self.name}] $ {' '.join(cmd)}")
        self.proc.start(cmd[0], cmd[1:])
        return True

    def stop(self) -> None:
        if self.proc is None:
            return

        if self.proc.state() != QProcess.NotRunning:
            self.output.emit(f"[{self.name}] stopping...")
            self.proc.terminate()

            if not self.proc.waitForFinished(3000):
                self.output.emit(f"[{self.name}] terminate timed out; killing process.")
                self.proc.kill()
                self.proc.waitForFinished(3000)

        self.proc = None

    def _read_output(self) -> None:
        if not self.proc:
            return

        text = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")

        for line in text.rstrip().splitlines():
            self.output.emit(f"[{self.name}] {line}")

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self.output.emit(f"[{self.name}] finished. exit_code={exit_code}")
        self.finished.emit(self.name, int(exit_code))

    def _error(self, error: QProcess.ProcessError) -> None:
        self.output.emit(f"[{self.name}] ERROR: process error {int(error)}")

        if error == QProcess.FailedToStart:
            self.failed_to_start.emit(self.name)


def build_sitl_command(
    profile: LauncherProfile,
    console: bool,
    mavproxy_map: bool,
    gcs_out: str,
    wipe_params: bool = False,
) -> tuple[list[str], Path]:
    args = [
        "./Tools/autotest/sim_vehicle.py",
        "-v",
        profile.aircraft.vehicle,
        "-f",
        profile.aircraft.frame,
        "-L",
        profile.start_location.name,
    ]

    if console:
        args.append("--console")

    if mavproxy_map:
        args.append("--map")

    if gcs_out.strip():
        args.append(f"--out={gcs_out.strip()}")

    if wipe_params:
        args.append("-w")

    param_file = profile.paths.resolve_project_path(profile.paths.param_file)

    if param_file.exists():
        args.append(f"--add-param-file={param_file}")

    shell_cmd = " ".join(shlex.quote(arg) for arg in args)

    return ["bash", "-lc", shell_cmd], profile.paths.ardupilot_root


def build_docker_sitl_command(
    profile: LauncherProfile,
    console: bool,
    mavproxy_map: bool,
    gcs_out: str,
    wipe_params: bool = False,
) -> tuple[list[str], Path]:
    project_root = profile.paths.project_root
    dockerfile = project_root / "docker" / "Dockerfile"
    param_file = profile.paths.resolve_project_path(profile.paths.param_file)

    sim_args = [
        "./Tools/autotest/sim_vehicle.py",
        "-v",
        profile.aircraft.vehicle,
        "-f",
        profile.aircraft.frame,
        "-L",
        profile.start_location.name,
    ]

    if console:
        sim_args.append("--console")

    if mavproxy_map:
        sim_args.append("--map")

    sim_args.append(f"--out={DOCKER_GCS_OUT}")

    if wipe_params:
        sim_args.append("-w")

    if param_file.exists():
        sim_args.append(
            f"--add-param-file=/workspace/omnitrainer-sitl/{param_file.relative_to(project_root)}"
        )

    inspect_cmd = " ".join(
        shlex.quote(arg)
        for arg in ["docker", "image", "inspect", DOCKER_IMAGE]
    )

    build_cmd = " ".join(
        shlex.quote(arg)
        for arg in [
            "docker",
            "build",
            "-t",
            DOCKER_IMAGE,
            "-f",
            str(dockerfile),
            str(project_root),
        ]
    )

    run_cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        DOCKER_CONTAINER,

        # TCP ports only. Do not publish UDP 14551 because QGC uses it on the host.
        "-p",
        "5760:5760/tcp",
        "-p",
        "5762:5762/tcp",

        "-e",
        "OMNI_WORKSPACE=/workspace/omnitrainer-sitl",
        "-e",
        f"OMNI_LOCATION_NAME={profile.start_location.name}",
        "-e",
        f"OMNI_LOCATION_LAT={profile.start_location.lat:.7f}",
        "-e",
        f"OMNI_LOCATION_LNG={profile.start_location.lng:.7f}",
        "-e",
        f"OMNI_LOCATION_ALT_MSL={profile.start_location.alt_msl_m:.2f}",
        "-e",
        f"OMNI_LOCATION_HEADING={profile.start_location.heading_deg:.1f}",
        "-v",
        f"{project_root}:/workspace/omnitrainer-sitl:ro",
        DOCKER_IMAGE,
        *sim_args,
    ]

    cleanup_cmd = f"docker rm -f {DOCKER_CONTAINER} >/dev/null 2>&1 || true"

    shell_cmd = (
        f"({inspect_cmd} >/dev/null 2>&1 || {build_cmd}) "
        f"&& ({cleanup_cmd}) && "
        + " ".join(shlex.quote(arg) for arg in run_cmd)
    )

    return ["bash", "-lc", shell_cmd], project_root