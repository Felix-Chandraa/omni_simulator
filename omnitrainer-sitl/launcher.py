#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Handle PyInstaller bundled paths
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running as PyInstaller bundle
    BASE_PATH = Path(sys._MEIPASS)
    sys.path.insert(0, str(BASE_PATH))
else:
    # Running from source
    BASE_PATH = Path(__file__).parent

from omni_launcher.config import DEFAULT_PROFILE, ProfileError


def main() -> int:
    # Resolve profile path relative to bundled base if needed
    if len(sys.argv) > 1:
        profile = Path(sys.argv[1])
        if not profile.is_absolute():
            # Try bundled location first
            bundled_profile = BASE_PATH / sys.argv[1]
            profile = bundled_profile if bundled_profile.exists() else profile
    else:
        profile = BASE_PATH / DEFAULT_PROFILE if (BASE_PATH / DEFAULT_PROFILE).exists() else DEFAULT_PROFILE
    try:
        from omni_launcher.ui.main_window import run_app

        return run_app(profile)
    except ProfileError as exc:
        print(f"Profile error: {exc}", file=sys.stderr)
        return 2
    except ModuleNotFoundError as exc:
        if "QtWebEngine" in str(exc) or "PyQt5" in str(exc):
            print("Missing Qt WebEngine support.", file=sys.stderr)
            print("Install Ubuntu packages: python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel", file=sys.stderr)
            return 3
        raise


if __name__ == "__main__":
    raise SystemExit(main())
