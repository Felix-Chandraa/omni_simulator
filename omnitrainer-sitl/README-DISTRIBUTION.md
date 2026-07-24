# Omni Trainer SITL Launcher - Standalone Distribution

This package contains the Omni Trainer SITL Launcher as a standalone executable binary.

## Quick Start

### Option 1: Automatic Installation (Recommended)

```bash
# Make everything executable
chmod +x install.sh omni-trainer-sitl

# Run the installer (installs dependencies and optionally ArduPilot)
./install.sh

# Then run the launcher
./omni-trainer-sitl
```

### Option 2: Manual Installation

1. **Install system dependencies:**
   - Ubuntu/Debian:
     ```bash
     sudo apt-get update
     sudo apt-get install -y python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel xterm
     ```
   - macOS:
     ```bash
     brew install pyqt5 git
     ```

2. **Install Python dependencies:**
   ```bash
   pip install --user PyYAML pymavlink MAVProxy
   # If Python reports an externally managed environment:
   pip install --user --break-system-packages PyYAML pymavlink MAVProxy
   ```

3. **Install ArduPilot (optional but recommended):**
   ```bash
   git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git ~/ardupilot
   ~/ardupilot/Tools/environment_install/install-prereqs-ubuntu.sh -y
   ```

4. **Run the launcher:**
   ```bash
   chmod +x omni-trainer-sitl
   ./omni-trainer-sitl
   ```

## Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 18.04+, Debian 10+) or macOS 10.14+
- **Python**: 3.8 or later (included in binary)
- **RAM**: 2GB minimum
- **Disk**: 500MB free space

### Runtime Dependencies
The binary includes most dependencies, but your system must have:
- PyQt5 graphics libraries (`python3-pyqt5`, `python3-pyqt5.qtwebengine`)
- MAVProxy and pymavlink (`pip install --user PyYAML pymavlink MAVProxy`, or add `--break-system-packages` on externally managed Python installs)
- xterm (for SITL console)

### Optional: ArduPilot SITL
For full functionality, install ArduPilot SITL:
```bash
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git ~/ardupilot
```

The launcher automatically checks `OMNI_ARDUPILOT_ROOT`, then `$HOME/ardupilot`, then legacy checkout paths. You can specify:
```bash
OMNI_ARDUPILOT_ROOT=/path/to/ardupilot ./omni-trainer-sitl
```

## Usage

### Launching the Application
```bash
./omni-trainer-sitl
```

### With Custom Profile
```bash
./omni-trainer-sitl /path/to/custom_profile.yaml
```

### With Custom ArduPilot Location
```bash
OMNI_ARDUPILOT_ROOT=/path/to/ardupilot ./omni-trainer-sitl
```

### With Docker SITL
Install Docker through `./install.sh`, then enable **Docker SITL** in the launcher before pressing **Start SITL** or **Start All**. The first Docker run builds `omnitrainer-sitl:local`; later runs reuse it.

Headless Docker SITL:

```bash
bash scripts/docker_sitl.sh
```

Compose:

```bash
docker compose up --build sitl
```

Docker mode uses host networking so QGroundControl can receive telemetry on UDP `14550`.

## First Time Setup

1. Run `./install.sh` to install all dependencies
2. The launcher GUI will appear
3. Select your start location on the map
4. Click "Start All" to begin SITL simulation
5. Use "Fetch Terrain Altitude" to set home altitude
6. Monitor EFI and rangefinder injection in real-time

## Troubleshooting

### Binary won't run: "Permission denied"
```bash
chmod +x omni-trainer-sitl
./omni-trainer-sitl
```

### "QtWebEngine not found" error
Install PyQt5 WebEngine:
```bash
pip install --user PyQt5-sip PyQt5 PyQtWebEngine
# If Python reports an externally managed environment:
pip install --user --break-system-packages PyQt5-sip PyQt5 PyQtWebEngine
# Or on Ubuntu:
sudo apt-get install python3-pyqt5.qtwebengine
```

### "MAVProxy not found" error
```bash
pip install --user MAVProxy pymavlink
# If Python reports an externally managed environment:
pip install --user --break-system-packages MAVProxy pymavlink
```

### SITL won't start: "sim_vehicle.py not found"
Install ArduPilot:
```bash
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git ~/ardupilot
```

### Terrain altitude fetch not working
- Check internet connection (uses OpenTopoData API)
- Try again - API sometimes times out
- Manual altitude entry still available as fallback

## Features

✅ **Interactive Map** - Click to place aircraft start location  
✅ **Terrain Altitude** - Automatic elevation lookup with manual override  
✅ **EFI Simulator** - Real-time engine telemetry injection  
✅ **Rangefinder** - Terrain-relative altitude injection  
✅ **Aviation Overlay** - Nearby airports and navigation aids  
✅ **Live Telemetry** - Monitor SITL via MAVProxy  
✅ **Parameter Management** - Load/reset ArduPilot parameters  

## File Structure

```
omni-trainer-sitl           # Main executable binary
install.sh                  # Dependency installer
README-DISTRIBUTION.md      # This file
profiles/                   # Configuration profiles
  omni_trainer_dle30_15kg.yaml
scripts/                    # Helper scripts (included in binary)
  omni_efi_mavlink_sim.py
  omni_rangefinder_mavlink_sim.py
assets/                     # Aircraft models (included in binary)
  ardupilot/aircraft/Omni-Trainer/
```

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Ubuntu 18.04+ | ✅ Tested | Recommended |
| Debian 10+ | ✅ Supported | Similar to Ubuntu |
| macOS 10.14+ | ⚠️ Partial | Build required |
| Fedora/RHEL | ⚠️ Unknown | Should work, untested |

## Building from Source

If you need to rebuild the binary:

```bash
git clone https://github.com/yourusername/omnitrainer-sitl.git
cd omnitrainer-sitl
bash ./build_binary.sh
```

The binary will be created at `dist/omni-trainer-sitl`.

## Support & Issues

For issues, questions, or suggestions:
- Check the troubleshooting section above
- Review launcher logs in the GUI output panel
- Ensure all dependencies are installed via `./install.sh`

## License

See LICENSE file in the repository.

## Version

- **Omni Trainer SITL Launcher**: 1.0
- **Python**: 3.10.12
- **Build Date**: June 19, 2026

---

**Note**: This is a standalone binary distribution. The full source code is available at the project repository.
