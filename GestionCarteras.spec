 # -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_dir = Path.cwd()
collected_datas = [
    ('assets', 'assets'),
    ('.env', '.')
]


a = Analysis(
    ['main.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=collected_datas,
    hiddenimports=['tkcalendar', 'babel.numbers'],
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
    a.zipfiles,
    a.datas,
    [],
    name='NeonBlue',
    icon=str(project_dir / 'assets' / 'icons' / 'home.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
