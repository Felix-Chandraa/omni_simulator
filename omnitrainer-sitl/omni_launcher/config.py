from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_PROFILE = Path("profiles/omni_trainer_dle30_15kg.yaml")
ARDUPILOT_SENTINEL = Path("Tools/autotest/sim_vehicle.py")


@dataclass
class AircraftConfig:
    name: str
    vehicle: str
    frame: str


@dataclass
class GeometryConfig:
    weight_kg: float
    wing_area_m2: float
    cruise_speed_mps: float


@dataclass
class EngineConfig:
    name: str
    propeller_inch: int
    efi_enabled: bool


@dataclass
class PathsConfig:
    project_root: Path
    ardupilot_root: Path
    efi_script: str
    rangefinder_script: str
    param_file: str

    def resolve_ardupilot_path(self, value: str) -> Path:
        path = expand_profile_path(value)
        if path.is_absolute():
            return path
        return self.ardupilot_root / path

    def resolve_project_path(self, value: str) -> Path:
        path = expand_profile_path(value)
        if path.is_absolute():
            return path
        return self.project_root / path


@dataclass
class NetworkConfig:
    gcs_out: str
    efi_connect: str
    telemetry_gcs_out: str


@dataclass
class StartLocationConfig:
    name: str
    lat: float
    lng: float
    alt_msl_m: float
    heading_deg: float
    alt_offset_m: float
    altitude_unit: str = "m"


@dataclass
class MapConfig:
    enabled: bool
    default_zoom: int
    tile_provider: str
    aviation_overlay_enabled: bool
    aviation_radius_km: float
    cache_max_age_days: int


@dataclass
class EfiConfig:
    rate_hz: int
    print_rate_hz: int
    rpm_idle: int
    rpm_cruise: int
    rpm_max: int
    cht_min_c: float
    cht_cruise_c: float
    fuel_flow_idle_lph: float
    fuel_flow_cruise_lph: float
    fuel_flow_max_lph: float
    force_running: bool = False
    simulate_egt: bool = True
    simulate_fuel_flow: bool = True
    rng_inject: bool = True


@dataclass
class RangefinderConfig:
    enabled: bool
    rate_hz: int
    print_rate_hz: int
    min_cm: int
    max_cm: int
    sensor_id: int


@dataclass
class LauncherProfile:
    path: Path
    aircraft: AircraftConfig
    geometry: GeometryConfig
    engine: EngineConfig
    paths: PathsConfig
    network: NetworkConfig
    start_location: StartLocationConfig
    map: MapConfig
    efi: EfiConfig
    rangefinder: RangefinderConfig


class ProfileError(ValueError):
    pass


def expand_profile_value(value: str) -> str:
    """Expand shell-style environment references used in YAML profiles.

    Supports $HOME, ${HOME}, and ${VAR:-fallback}. The fallback form keeps
    profiles portable without requiring users to edit machine-specific paths.
    """
    text = str(value)

    def replace_default(match: re.Match[str]) -> str:
        name = match.group(1)
        fallback = match.group(2)
        return os.environ.get(name) or expand_profile_value(fallback)

    text = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\:-(.*?)\}", replace_default, text)
    return os.path.expandvars(os.path.expanduser(text))


def expand_profile_path(value: str) -> Path:
    return Path(expand_profile_value(value)).expanduser()


def find_ardupilot_root(value: str | Path = "auto") -> Path:
    """Resolve the local ArduPilot checkout without baking in one host path."""
    raw = expand_profile_value(str(value)).strip()
    if not raw or raw.lower() == "auto":
        env_root = os.environ.get("OMNI_ARDUPILOT_ROOT")
        if env_root:
            return Path(env_root).expanduser()
        candidates = [
            Path.home() / "ardupilot",
            Path.home() / "ArduPilot" / "ardupilot",
            Path.home() / "ArduSITL" / "ardupilot",
        ]
        for candidate in candidates:
            if candidate and (candidate / ARDUPILOT_SENTINEL).exists():
                return candidate.resolve()
        for candidate in candidates:
            if candidate:
                return candidate
        return Path.home() / "ardupilot"
    return Path(raw).expanduser()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ProfileError(f"Missing or invalid '{name}' section in profile.")
    return value


def _require(section: dict[str, Any], key: str, section_name: str) -> Any:
    if key not in section or section[key] is None:
        raise ProfileError(f"Missing required profile field: {section_name}.{key}")
    return section[key]


def _profile_project_root(profile_path: Path) -> Path:
    candidates = [profile_path.parent, profile_path.parent.parent]
    markers = ("omnisitl.param", "scripts", "assets")
    for candidate in candidates:
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return profile_path.parent.parent


def _as_float(section: dict[str, Any], key: str, section_name: str) -> float:
    try:
        return float(_require(section, key, section_name))
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"Profile field {section_name}.{key} must be a number.") from exc


def _as_int(section: dict[str, Any], key: str, section_name: str) -> int:
    try:
        return int(_require(section, key, section_name))
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"Profile field {section_name}.{key} must be an integer.") from exc


def _as_bool(section: dict[str, Any], key: str, section_name: str, default: bool | None = None) -> bool:
    if key not in section or section[key] is None:
        if default is not None:
            return default
        raise ProfileError(f"Missing required profile field: {section_name}.{key}")
    value = section[key]
    if isinstance(value, bool):
        return value
    raise ProfileError(f"Profile field {section_name}.{key} must be true or false.")


def _as_altitude_unit(section: dict[str, Any], key: str, section_name: str) -> str:
    value = str(section.get(key, "m")).strip().lower()
    if value in {"m", "meter", "meters", "metre", "metres"}:
        return "m"
    if value in {"ft", "foot", "feet"}:
        return "ft"
    raise ProfileError(f"Profile field {section_name}.{key} must be 'm' or 'ft'.")


def load_profile(path: str | Path) -> LauncherProfile:
    profile_path = Path(path).expanduser()
    if not profile_path.is_absolute():
        profile_path = (Path.cwd() / profile_path).resolve()
    if not profile_path.exists():
        raise ProfileError(f"Profile file not found: {profile_path}")

    try:
        raw = yaml.safe_load(profile_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"Could not parse YAML profile: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError("Profile root must be a YAML mapping.")

    aircraft = _section(raw, "aircraft")
    geometry = _section(raw, "geometry")
    engine = _section(raw, "engine")
    paths = _section(raw, "paths")
    network = _section(raw, "network")
    start = _section(raw, "start_location")
    map_cfg = _section(raw, "map")
    efi = _section(raw, "efi")
    rangefinder = _section(raw, "rangefinder")

    ardupilot_root = find_ardupilot_root(str(_require(paths, "ardupilot_root", "paths")))
    project_root = _profile_project_root(profile_path)

    return LauncherProfile(
        path=profile_path,
        aircraft=AircraftConfig(
            name=str(_require(aircraft, "name", "aircraft")),
            vehicle=str(_require(aircraft, "vehicle", "aircraft")),
            frame=str(_require(aircraft, "frame", "aircraft")),
        ),
        geometry=GeometryConfig(
            weight_kg=_as_float(geometry, "weight_kg", "geometry"),
            wing_area_m2=_as_float(geometry, "wing_area_m2", "geometry"),
            cruise_speed_mps=_as_float(geometry, "cruise_speed_mps", "geometry"),
        ),
        engine=EngineConfig(
            name=str(_require(engine, "name", "engine")),
            propeller_inch=_as_int(engine, "propeller_inch", "engine"),
            efi_enabled=_as_bool(engine, "efi_enabled", "engine"),
        ),
        paths=PathsConfig(
            project_root=project_root,
            ardupilot_root=ardupilot_root,
            efi_script=expand_profile_value(str(_require(paths, "efi_script", "paths"))),
            rangefinder_script=expand_profile_value(str(_require(paths, "rangefinder_script", "paths"))),
            param_file=expand_profile_value(str(_require(paths, "param_file", "paths"))),
        ),
        network=NetworkConfig(
            gcs_out=str(_require(network, "gcs_out", "network")),
            efi_connect=str(_require(network, "efi_connect", "network")),
            telemetry_gcs_out=str(_require(network, "telemetry_gcs_out", "network")),
        ),
        start_location=StartLocationConfig(
            name=str(_require(start, "name", "start_location")),
            lat=_as_float(start, "lat", "start_location"),
            lng=_as_float(start, "lng", "start_location"),
            alt_msl_m=_as_float(start, "alt_msl_m", "start_location"),
            heading_deg=_as_float(start, "heading_deg", "start_location"),
            alt_offset_m=_as_float(start, "alt_offset_m", "start_location"),
            altitude_unit=_as_altitude_unit(start, "altitude_unit", "start_location"),
        ),
        map=MapConfig(
            enabled=_as_bool(map_cfg, "enabled", "map"),
            default_zoom=_as_int(map_cfg, "default_zoom", "map"),
            tile_provider=str(_require(map_cfg, "tile_provider", "map")),
            aviation_overlay_enabled=_as_bool(map_cfg, "aviation_overlay_enabled", "map"),
            aviation_radius_km=_as_float(map_cfg, "aviation_radius_km", "map"),
            cache_max_age_days=_as_int(map_cfg, "cache_max_age_days", "map"),
        ),
        efi=EfiConfig(
            rate_hz=_as_int(efi, "rate_hz", "efi"),
            print_rate_hz=_as_int(efi, "print_rate_hz", "efi"),
            rpm_idle=_as_int(efi, "rpm_idle", "efi"),
            rpm_cruise=_as_int(efi, "rpm_cruise", "efi"),
            rpm_max=_as_int(efi, "rpm_max", "efi"),
            cht_min_c=_as_float(efi, "cht_min_c", "efi"),
            cht_cruise_c=_as_float(efi, "cht_cruise_c", "efi"),
            fuel_flow_idle_lph=_as_float(efi, "fuel_flow_idle_lph", "efi"),
            fuel_flow_cruise_lph=_as_float(efi, "fuel_flow_cruise_lph", "efi"),
            fuel_flow_max_lph=_as_float(efi, "fuel_flow_max_lph", "efi"),
            force_running=_as_bool(efi, "force_running", "efi", default=False),
            simulate_egt=_as_bool(efi, "simulate_egt", "efi", default=True),
            simulate_fuel_flow=_as_bool(efi, "simulate_fuel_flow", "efi", default=True),
            rng_inject=_as_bool(efi, "rng_inject", "efi", default=True),
        ),
        rangefinder=RangefinderConfig(
            enabled=_as_bool(rangefinder, "enabled", "rangefinder"),
            rate_hz=_as_int(rangefinder, "rate_hz", "rangefinder"),
            print_rate_hz=_as_int(rangefinder, "print_rate_hz", "rangefinder"),
            min_cm=_as_int(rangefinder, "min_cm", "rangefinder"),
            max_cm=_as_int(rangefinder, "max_cm", "rangefinder"),
            sensor_id=_as_int(rangefinder, "sensor_id", "rangefinder"),
        ),
    )
