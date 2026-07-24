# Omni Trainer SITL Launcher

Omni Trainer SITL Launcher is a Qt launcher for running the Omni Trainer fixed-wing aircraft in ArduPlane SITL. It keeps the original map-first workflow while moving aircraft, path, network, start location, map, aviation overlay, and EFI settings into a YAML profile.

## Aircraft Profile

The default profile is `profiles/omni_trainer_dle30_15kg.yaml`.

- Aircraft: Omni Trainer
- Engine: DLE30 gasoline engine
- Propeller: 18 inch
- Weight: 15 kg
- Wing area: 0.75 m2
- Cruise speed: 23 m/s
- Backend: ArduPlane SITL with default plane model
- EFI: MAVLink injector script

The default profile is portable. It uses:

```yaml
paths:
  ardupilot_root: "auto"
```

The launcher checks `OMNI_ARDUPILOT_ROOT`, then `~/ardupilot`, then legacy checkout paths. Set `OMNI_ARDUPILOT_ROOT` only if you want to use a different ArduPilot tree.

## Install

Ubuntu system packages:

```bash
bash scripts/setup_ubuntu.sh
```

The installer also installs Python requirements, clones ArduPilot into `$HOME/ardupilot` by default, initializes submodules, and runs ArduPilot's Ubuntu prerequisite helper when available.

Bundled portable payloads:

- Aircraft model files: `assets/ardupilot/aircraft/Omni-Trainer`
- EFI injector: `scripts/omni_efi_mavlink_sim.py`
- Rangefinder terrain-distance injector: `scripts/omni_rangefinder_mavlink_sim.py`
- Default SITL params: `omnisitl.param`

To use an existing ArduPilot checkout:

```bash
OMNI_ARDUPILOT_ROOT=/path/to/ardupilot bash scripts/setup_ubuntu.sh
```

The GUI uses PyQt5 QtWebEngine for the interactive Leaflet map. If the map widget fails to import, install:

```bash
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel
```

## Run

Recommended launcher command:

```bash
./launch.sh
```

`launch.sh` checks the full runtime stack before opening the GUI. If something fixable is missing, it runs `scripts/setup_ubuntu.sh`, validates the profile, and only launches when everything passes. If it cannot fix the issue, it aborts with the failing requirement.

```bash
python3 launcher.py
```

You can also pass a profile path:

```bash
python3 launcher.py profiles/omni_trainer_dle30_15kg.yaml
```

## Docker SITL

Docker mode runs ArduPilot SITL inside a container while keeping the launcher GUI and QGroundControl native on the host.

On a fresh device:

```bash
bash scripts/setup_ubuntu.sh
./launch.sh
```

In the GUI, enable **Docker SITL** before pressing **Start**. The first run builds the local image `omnitrainer-sitl:local`, so it can take several minutes. Later runs reuse the image.

Headless Docker SITL is also available:

```bash
bash scripts/docker_sitl.sh
```

Or with Compose:

```bash
docker compose up --build sitl
```

Docker SITL uses host networking so QGroundControl can keep listening on UDP `14550`.

## Map Workflow

The map opens at the configured start location. Click the map or drag the marker to update latitude and longitude in the Start Location panel. Use **Altitude unit** to enter home altitude and offset in meters or feet; the launcher converts values back to meters before writing the ArduPilot start location. Use **Fetch Terrain Altitude** to query terrain elevation and apply the configured altitude offset. Manual altitude entry remains available if the lookup fails.

The map includes selectable base layers and an aviation overlay. If tiles fail to load or the internet is unavailable, the launcher stays usable and the start marker still works.

## Aviation Overlay

The aviation overlay uses OurAirports public CSV data for airports and navaids near the selected operating area. The filter radius and cache age come from the YAML profile. Overlay data is cached under `~/.omni_trainer_sitl_launcher/aviation`.

Use **Refresh Aviation Overlay** to download and filter fresh data. If the download fails, the launcher uses cache when available. If no cache exists, it falls back to a WICM marker and logs a warning.

## Starting SITL

Use **Validate Setup** before launch. The validation checks:

- ArduPilot root
- `Tools/autotest/sim_vehicle.py`
- Omni Trainer aircraft model directory
- bundled EFI script when enabled
- bundled rangefinder script when enabled
- Python executable
- required Python modules

- `locations.txt`
- QtWebEngine availability

Use **Start** to write the selected start location into ArduPilot `locations.txt`, start ArduPlane SITL, wait for the telemetry TCP port, then start the EFI injector and rangefinder injector when enabled. **Stop** kills all launched processes.

The SITL option **Reset params** is enabled by default. Keep it enabled when changing bundled model/takeoff params, because ArduPilot SITL stores parameters between runs.

## Commands

SITL command shape:

```bash
./Tools/autotest/sim_vehicle.py -v ArduPlane -f plane -L GUI_OMNI --console --map --out=udp:127.0.0.1:14550
```

The launcher also adds the bundled parameter file with `--add-param-file`, enabling EFI and MAVLink rangefinder parameters for SITL.

EFI command shape:

```bash
python3 scripts/omni_efi_mavlink_sim.py --connect tcp:127.0.0.1:5762 --rate 10 --print-rate 2
```

Rangefinder command shape:

```bash
python3 scripts/omni_rangefinder_mavlink_sim.py --connect tcp:127.0.0.1:5762 --rate 10 --print-rate 2 --min-cm 30 --max-cm 4500 --sensor-id 0
```

Both telemetry scripts can mirror messages directly to QGroundControl using `network.telemetry_gcs_out`, defaulting to `udpout:127.0.0.1:14550`. This helps QGC see `EFI_STATUS` and `DISTANCE_SENSOR` in MAVLink Inspector even if SITL forwarding does not show them.

The profile stores additional EFI engine values for future use, but the launcher only passes parameters supported by the current injector command.

## Troubleshooting

- **Map is blank:** check QtWebEngine packages. Online tiles are optional; marker selection still works once the widget loads.

- **EFI or rangefinder does not start:** confirm SITL exposes `tcp:127.0.0.1:5762`. The launcher waits for that TCP port before launching telemetry injectors.
- **QGroundControl does not show EFI/rangefinder:** open MAVLink Inspector and check `EFI_STATUS` and `DISTANCE_SENSOR`. Keep `network.telemetry_gcs_out` set to `udpout:127.0.0.1:14550`, or adjust it to the UDP port QGC is listening on.
- **Terrain lookup fails:** enter Home altitude MSL manually.
- **Aviation overlay fails:** refresh when online, or use cached/fallback overlay for simulation.

## Known Limitations

OurAirports data is not authoritative for real flight. The launcher is for simulation workflows. This refactor does not change ArduPilot aircraft physics files or the EFI injector implementation.
