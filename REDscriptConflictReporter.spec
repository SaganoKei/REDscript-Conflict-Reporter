# -*- mode: python ; coding: utf-8 -*-
import os, sys
from pathlib import Path

datas = []
binaries = []
hiddenimports = ['tkwebview2','tkwebview2.tkwebview2']

# Resolve base directory reliably (PyInstaller sets spec file CWD when executing)
try:
    base = Path(os.getcwd())
except Exception:
    base = Path('.')

# Include i18n JSON bundles (source i18n/ and dist/i18n/ if present)
for rel in (Path('i18n'), Path('dist') / 'i18n'):
    p = base / rel
    if p.is_dir():
        for json_file in p.glob('*.json'):
            datas.append((str(json_file), 'i18n'))

# Include assets (templates, stylesheets, config files)
for rel in (Path('assets'), Path('dist') / 'assets'):
    p = base / rel
    if p.is_dir():
        for asset_file in p.glob('*'):
            if asset_file.is_file():
                datas.append((str(asset_file), 'assets'))


a = Analysis(
    ['gui_conflict_report.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='REDscriptConflictReporter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
