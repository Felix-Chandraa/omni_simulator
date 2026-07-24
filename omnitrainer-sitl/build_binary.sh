#!/bin/bash
# Build script for Omni Trainer SITL Launcher standalone binary

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

echo "=========================================="
echo "Omni Trainer SITL Launcher - Binary Build"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "[INFO] Python version: $PYTHON_VERSION"

# Check dependencies
echo "[INFO] Checking dependencies..."
python3 -c "import PyQt5" 2>/dev/null || { echo "[ERROR] PyQt5 not installed. Run: pip install PyQt5 PyQt5.sip"; exit 1; }
python3 -c "import pymavlink" 2>/dev/null || { echo "[ERROR] pymavlink not installed. Run: pip install pymavlink"; exit 1; }
python3 -c "import MAVProxy" 2>/dev/null || { echo "[ERROR] MAVProxy not installed. Run: pip install MAVProxy"; exit 1; }
python3 -c "import yaml" 2>/dev/null || { echo "[ERROR] PyYAML not installed. Run: pip install PyYAML"; exit 1; }
echo "[OK] All dependencies installed"
echo ""

# Run PyInstaller
echo "[INFO] Building standalone binary with PyInstaller..."
cd "$PROJECT_ROOT"
pyinstaller \
  --onefile \
  --windowed \
  --name "omni-trainer-sitl" \
  --icon=None \
  --specpath "$BUILD_DIR" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR/build" \
  --add-data "$PROJECT_ROOT/profiles:profiles" \
  --add-data "$PROJECT_ROOT/scripts:scripts" \
  --add-data "$PROJECT_ROOT/assets:assets" \
  --add-data "$PROJECT_ROOT/docker:docker" \
  --add-data "$PROJECT_ROOT/docker-compose.yml:." \
  --add-data "$PROJECT_ROOT/.dockerignore:." \
  --add-data "$PROJECT_ROOT/omnisitl.param:." \
  --add-data "$PROJECT_ROOT/README.md:." \
  --add-data "$PROJECT_ROOT/requirements.txt:." \
  --hidden-import=PyQt5.QtCore \
  --hidden-import=PyQt5.QtGui \
  --hidden-import=PyQt5.QtWidgets \
  --hidden-import=PyQt5.QtWebEngineWidgets \
  --hidden-import=PyQt5.QtWebChannel \
  --hidden-import=pymavlink \
  --hidden-import=pymavlink.dialects \
  --hidden-import=pymavlink.dialects.v10 \
  --hidden-import=pymavlink.dialects.v20 \
  --hidden-import=MAVProxy \
  --hidden-import=yaml \
  "$PROJECT_ROOT/launcher.py" \
  2>&1 | grep -v "WARNING.*splash" || true

echo ""

# Check if build succeeded
if [ -f "$DIST_DIR/omni-trainer-sitl" ]; then
  BINARY_PATH="$DIST_DIR/omni-trainer-sitl"
  BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
  
  echo "=========================================="
  echo "[SUCCESS] Binary built successfully!"
  echo "=========================================="
  echo ""
  echo "Binary location: $BINARY_PATH"
  echo "Binary size: $BINARY_SIZE"
  echo ""
  echo "To run on another machine:"
  echo "  1. Copy the binary to the target machine"
  echo "  2. Make it executable: chmod +x omni-trainer-sitl"
  echo "  3. Run it: ./omni-trainer-sitl"
  echo ""
  echo "Important: The target machine must have:"
  echo "  - Python 3.8+ installed"
  echo "  - PyQt5 libraries (python3-pyqt5, python3-pyqt5.qtwebengine)"
  echo "  - MAVProxy and pymavlink installed"
  echo "  - ArduPilot installed at \$HOME/ardupilot, or set OMNI_ARDUPILOT_ROOT"
  echo ""
else
  echo "[ERROR] Binary build failed!"
  exit 1
fi
