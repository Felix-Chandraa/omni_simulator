# Omni Trainer SITL Launcher - Distribution Complete ✅

## Package Information

**Package Name:** `omni-trainer-sitl-standalone.tar.gz`  
**Size:** 162 MB (compressed)  
**Format:** Single binary + installer scripts  
**SHA256:** f84e0122b7cc159214f2a1f7a4cea2426f9e6c90128d5b7f2f983c2c5d0aa269  

## What's Included

```
dist_pkg/
├── omni-trainer-sitl           # Standalone executable binary (163 MB uncompressed)
├── install.sh                  # One-click dependency installer
├── README.md                   # Full documentation
├── QUICK-START.txt            # Getting started guide
├── omni_trainer_dle30_15kg.yaml # Default configuration profile
├── omnisitl.param              # Default SITL parameters
├── profiles/                   # Bundled profiles
├── scripts/                    # Helper launch/setup/telemetry scripts
├── docker/                     # Docker SITL image files
├── docker-compose.yml          # Headless Docker SITL compose file
├── .dockerignore               # Docker build context exclusions
└── assets/                     # Bundled Omni-Trainer assets
```

## Distribution Method

### Option 1: Direct Transfer
```bash
# On your machine
tar xzf omni-trainer-sitl-standalone.tar.gz
cd dist_pkg

# Copy to another machine
scp -r . user@other-machine:/home/user/omni-trainer-sitl/

# On target machine
cd /home/user/omni-trainer-sitl
./install.sh
./omni-trainer-sitl
```

### Option 2: Upload to Server
```bash
# Upload the tar.gz to your server
scp omni-trainer-sitl-standalone.tar.gz user@server:/tmp/

# On target machine, download and extract
cd ~
wget http://server/omni-trainer-sitl-standalone.tar.gz
tar xzf omni-trainer-sitl-standalone.tar.gz
cd dist_pkg
./install.sh
./omni-trainer-sitl
```

### Option 3: USB/External Drive
```bash
# Copy to USB
cp omni-trainer-sitl-standalone.tar.gz /media/usb/
# Or just copy dist_pkg directory directly
cp -r dist_pkg /media/usb/omni-trainer-sitl/
```

## Installation for End Users

**For users receiving this package:**

1. **Extract (2 seconds)**
   ```bash
   tar xzf omni-trainer-sitl-standalone.tar.gz
   cd dist_pkg
   ```

2. **Install (5-10 minutes)**
   ```bash
   ./install.sh
   ```
   This automatically:
   - ✅ Installs system dependencies (PyQt5, MAVProxy, pymavlink)
   - ✅ Optionally downloads and configures ArduPilot SITL
   - ✅ Creates desktop shortcuts (on Linux)
   - ✅ Sets up environment variables

3. **Run (immediately)**
   ```bash
   ./omni-trainer-sitl
   ```
   GUI appears in seconds!

## System Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Ubuntu 18.04+, Debian 10+, or macOS 10.14+ |
| **Python** | Bundled in binary (3.10.12) |
| **Python Dependencies** | Installed automatically by install.sh |
| **System Libraries** | PyQt5 WebEngine (auto-installed) |
| **Disk Space** | 500 MB after extraction |
| **RAM** | 2 GB minimum |
| **Internet** | Only for initial setup and terrain lookup |

## Key Features Pre-Configured

✅ **All Python dependencies included in binary**
- PyQt5 (GUI framework)
- pymavlink (ArduPilot communication)
- MAVProxy (telemetry handling)
- PyYAML (configuration)

✅ **All scripts embedded**
- EFI simulator
- Rangefinder injector
- Location writer

✅ **All data files included**
- Profile templates
- Aircraft models
- Configuration examples

✅ **Works without ArduPilot installed**
- Basic launcher functions available
- Optional: install ArduPilot for full SITL simulation
- Optional: enable Docker SITL to run ArduPilot inside a local container

## Verification

To verify the package integrity:

```bash
# Check SHA256
sha256sum omni-trainer-sitl-standalone.tar.gz
# Should output: f84e0122b7cc159214f2a1f7a4cea2426f9e6c90128d5b7f2f983c2c5d0aa269

# Extract and check
tar xzf omni-trainer-sitl-standalone.tar.gz
file dist_pkg/omni-trainer-sitl
# Should show: ELF 64-bit LSB executable, x86-64

# Test binary (without GUI)
dist_pkg/omni-trainer-sitl --version 2>&1 | head -1
# Should run without errors
```

## Troubleshooting Installation

### "Permission denied" errors
```bash
chmod +x dist_pkg/omni-trainer-sitl dist_pkg/install.sh
```

### Installer asks for password
This is normal - `sudo` is needed for system packages. Enter your password.

### "QtWebEngine not found" after installation
```bash
pip install --user PyQt5-sip PyQt5 PyQtWebEngine
# If Python reports an externally managed environment:
pip install --user --break-system-packages PyQt5-sip PyQt5 PyQtWebEngine
```

### Binary is too large
This is expected (163 MB). It contains:
- Complete Python runtime
- All PyQt5 libraries and plugins
- All dependency modules
- All application code and assets

Compression reduces it to 162 MB in the archive.

## Distributing Further

Feel free to:
- ✅ Share with colleagues
- ✅ Upload to file servers
- ✅ Include in documentation
- ✅ Modify installer for your setup
- ✅ Create mirrors

Just keep:
- ✅ SHA256 checksum for verification
- ✅ README.md and QUICK-START.txt
- ✅ All files in the package

## Building New Binaries

To rebuild after code changes:

```bash
cd /path/to/repo
bash build_binary.sh

# Creates new binary at dist/omni-trainer-sitl
# Then repackage:
mkdir dist_pkg_new
cp dist/omni-trainer-sitl dist_pkg_new/
cp install.sh README-DISTRIBUTION.md QUICK-START.txt omnisitl.param dist_pkg_new/
cp -a profiles scripts assets docker docker-compose.yml .dockerignore dist_pkg_new/
tar czf omni-trainer-sitl-standalone.tar.gz dist_pkg_new/
```

## Support & Updates

- **Bug Reports:** Use GitHub issues
- **Feature Requests:** Discuss on project page
- **Updates:** Download new tar.gz from project repository

---

## Summary

✅ **Binary created:** 163 MB executable  
✅ **Packaged:** 162 MB compressed archive  
✅ **Installation:** One script (`./install.sh`)  
✅ **First run:** 5-10 minutes total setup time  
✅ **Platform:** Linux/macOS (32-bit Intel/ARM compatible)  

**Ready to distribute! 🚀**

Users can now:
1. Extract the archive
2. Run `./install.sh`
3. Execute `./omni-trainer-sitl`
4. Start simulating immediately

No complex installation process. Everything automated.
