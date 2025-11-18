# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_dir = Path.cwd()
collected_datas = []

icons_dir = project_dir / 'assets' / 'icons'
if icons_dir.exists():
    for item in icons_dir.glob('*.png'):
        collected_datas.append((str(item), f"assets/icons/{item.name}"))

sounds_dir = project_dir / 'assets' / 'sounds'
if sounds_dir.exists():
    for item in sounds_dir.iterdir():
        if item.is_file():
            collected_datas.append((str(item), f"assets/sounds/{item.name}"))


a = Analysis(
    ['main.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=collected_datas,
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='GestionCarteras',
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GestionCarteras',
)
