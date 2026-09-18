# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Get absolute paths
app_root = os.path.abspath('.')

a = Analysis(
    ['gui_app.py'],
    pathex=[app_root],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('Logo', 'Logo'),
    ],
    hiddenimports=[
        'src',
        'src.core.inspector',
        'src.utils.config_manager',
        'src.tools.setup_roi',
        'scipy.signal',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='IC_Pin_Inspector',
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
    icon='Logo/tool.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IC_Pin_Inspector',
)
