from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import LauncherProfile
from .location_writer import locations_file_for_ardupilot
from .process_utils import python_executable


@dataclass
class ValidationItem:
    name: str
    ok: bool
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    items: list[ValidationItem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(item.ok or item.severity == "warning" for item in self.items)

    def add(self, name: str, ok: bool, message: str, severity: str = "error") -> None:
        self.items.append(ValidationItem(name, ok, message, severity))

    def summary(self) -> str:
        lines = []
        for item in self.items:
            status = "OK" if item.ok else item.severity.upper()
            lines.append(f"[{status}] {item.name}: {item.message}")
        return "\n".join(lines)


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def validate_setup(profile: LauncherProfile, efi_enabled: bool = True) -> ValidationResult:
    result = ValidationResult()
    root = profile.paths.ardupilot_root.expanduser()
    sim_vehicle = root / "Tools" / "autotest" / "sim_vehicle.py"
    model_name = profile.aircraft.frame.split(":", 1)[-1]
    model_dir = root / "Tools" / "autotest" / "aircraft" / model_name
    efi_script = profile.paths.resolve_project_path(profile.paths.efi_script)
    rangefinder_script = profile.paths.resolve_project_path(profile.paths.rangefinder_script)
    param_file = profile.paths.resolve_project_path(profile.paths.param_file)
    locations = locations_file_for_ardupilot(root)
    model_jsbsim = model_dir / "Omni-Trainer-JSBSim.xml"
    model_reset = model_dir / "reset.xml"
    model_engine = model_dir / "Engines" / "DLE30_EFI.xml"

    result.add("ArduPilot root", root.exists(), str(root))
    result.add("sim_vehicle.py", sim_vehicle.exists(), str(sim_vehicle))
    if profile.aircraft.frame.startswith("jsbsim:"):
        result.add("Aircraft model directory", model_dir.exists(), str(model_dir))
        result.add("Omni-Trainer JSBSim XML", model_jsbsim.exists(), str(model_jsbsim))
        result.add("Omni-Trainer reset XML", model_reset.exists(), str(model_reset))
        result.add("DLE30 engine XML", model_engine.exists(), str(model_engine))
    else:
        result.add("Aircraft model directory", True, f"Using built-in ArduPilot frame: {profile.aircraft.frame}", "warning")
    if efi_enabled:
        result.add("EFI script", efi_script.exists(), str(efi_script))
    else:
        result.add("EFI script", True, "EFI disabled for this run.", "warning")
    if profile.rangefinder.enabled:
        result.add("Rangefinder script", rangefinder_script.exists(), str(rangefinder_script))
    else:
        result.add("Rangefinder script", True, "Rangefinder disabled for this run.", "warning")
    result.add("SITL param file", param_file.exists(), str(param_file))
    result.add("Python executable", Path(python_executable()).exists() or shutil.which(python_executable()) is not None, python_executable())
    result.add("locations.txt", locations.exists(), str(locations))
    if profile.aircraft.frame.startswith("jsbsim:"):
        jsbsim_path = shutil.which("JSBSim") or shutil.which("jsbsim")
        result.add("JSBSim", jsbsim_path is not None, jsbsim_path or "Install package 'jsbsim' or add JSBSim to PATH.")
    else:
        result.add("JSBSim", True, "Not required for default ArduPilot model", "warning")
    for module_name in ("yaml", "pymavlink", "MAVProxy", "PyQt5"):
        result.add(f"Python module {module_name}", _module_available(module_name), "installed" if _module_available(module_name) else "missing")
    result.add("QtWebEngine", _module_available("PyQt5.QtWebEngineWidgets"), "PyQt5 QtWebEngine available" if _module_available("PyQt5.QtWebEngineWidgets") else "Install python3-pyqt5.qtwebengine.", "error")
    return result


def validate_docker_setup(profile: LauncherProfile, efi_enabled: bool = True) -> ValidationResult:
    result = ValidationResult()
    docker = shutil.which("docker")
    dockerfile = profile.paths.project_root / "docker" / "Dockerfile"
    entrypoint = profile.paths.project_root / "docker" / "entrypoint.sh"
    compose = profile.paths.project_root / "docker-compose.yml"
    model_source = profile.paths.project_root / "assets" / "ardupilot" / "aircraft" / "Omni-Trainer"
    efi_script = profile.paths.resolve_project_path(profile.paths.efi_script)
    rangefinder_script = profile.paths.resolve_project_path(profile.paths.rangefinder_script)
    param_file = profile.paths.resolve_project_path(profile.paths.param_file)

    result.add("Docker CLI", docker is not None, docker or "Install Docker Engine and make sure 'docker' is on PATH.")
    result.add("Dockerfile", dockerfile.exists(), str(dockerfile))
    result.add("Docker entrypoint", entrypoint.exists(), str(entrypoint))
    result.add("docker-compose.yml", compose.exists(), str(compose), "warning")
    result.add("Bundled aircraft assets", model_source.exists(), str(model_source))
    result.add("SITL param file", param_file.exists(), str(param_file))
    if efi_enabled:
        result.add("EFI script", efi_script.exists(), str(efi_script))
    else:
        result.add("EFI script", True, "EFI disabled for this run.", "warning")
    if profile.rangefinder.enabled:
        result.add("Rangefinder script", rangefinder_script.exists(), str(rangefinder_script))
    else:
        result.add("Rangefinder script", True, "Rangefinder disabled for this run.", "warning")
    for module_name in ("yaml", "pymavlink", "PyQt5"):
        result.add(f"Python module {module_name}", _module_available(module_name), "installed" if _module_available(module_name) else "missing")
    result.add("QtWebEngine", _module_available("PyQt5.QtWebEngineWidgets"), "PyQt5 QtWebEngine available" if _module_available("PyQt5.QtWebEngineWidgets") else "Install python3-pyqt5.qtwebengine.", "error")
    return result
