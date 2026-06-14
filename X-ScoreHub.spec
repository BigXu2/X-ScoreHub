# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for X-ScoreHub macOS .app bundle."""

import sys
from pathlib import Path

ROOT = Path('.')
APP_NAME = 'X-ScoreHub'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('pdf_repo', 'pdf_repo'),
        ('import-md', 'import-md'),
        ('scores.db', '.'),
        ('X-ScoreHub.png', '.'),
        ('CLAUDE.md', '.'),
        ('IMPORT_SONG_FORMAT.md', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=['PyQt5', 'fitz', 'app', 'app.database', 'app.importers',
                   'app.exporters', 'app.main_window', 'app.widgets',
                   'app.widgets.song_list', 'app.widgets.pdf_viewer',
                   'app.widgets.song_info', 'app.utils'],
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
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # --windowed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['X-ScoreHub.icns'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f'{APP_NAME}.app',
    icon='X-ScoreHub.icns',
    bundle_identifier='com.xscorehub.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.1',
        'CFBundleVersion': '1.1.0',
        'CFBundleName': 'X-ScoreHub',
        'CFBundleDisplayName': 'X-ScoreHub 乐谱浏览器',
        'LSMinimumSystemVersion': '11.0',
    },
)
