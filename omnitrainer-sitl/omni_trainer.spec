# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Omni Trainer SITL Launcher

import os
from pathlib import Path

block_cipher = None

# Project root
project_root = Path(__file__).parent

# Data files to include
datas = [
    (str(project_root / 'profiles'), 'profiles'),
    (str(project_root / 'scripts'), 'scripts'),
    (str(project_root / 'assets'), 'assets'),
    (str(project_root / 'docker'), 'docker'),
    (str(project_root / 'docker-compose.yml'), '.'),
    (str(project_root / '.dockerignore'), '.'),
    (str(project_root / 'omnisitl.param'), '.'),
    (str(project_root / 'README.md'), '.'),
    (str(project_root / 'requirements.txt'), '.'),
]

# Hidden imports required by the app
hidden_imports = [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtWebChannel',
    'pymavlink',
    'pymavlink.dialects',
    'pymavlink.dialects.v10',
    'pymavlink.dialects.v20',
    'MAVProxy',
    'yaml',
]

a = Analysis(
    [str(project_root / 'launcher.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='omni-trainer-sitl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
