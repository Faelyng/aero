# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

APP_NAME = "Aero Mission Planner"

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        (
            "example/Aircraft Mission Flight Plan Authorization Form 02032026.pdf",
            "example",
        ),
        ("AeroRoster20260127.json", "."),
        *collect_data_files("sv_ttk"),
        *collect_data_files("tkcalendar"),
        *collect_data_files("tzdata"),
    ],
    hiddenimports=[
        "babel.numbers",
        "babel.dates",
        "tzdata",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    # macOS: onedir wrapped in a .app bundle (onefile+BUNDLE is deprecated in PyInstaller 6)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        strip=False,
        upx=True,
        console=False,
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
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="org.slosar.aeromissionplanner",
    )
else:
    # Windows / Linux: single-file executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        strip=False,
        upx=True,
        console=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
