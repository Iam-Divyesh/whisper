"""Build script for creating executable."""
import os
import sys
import subprocess
from pathlib import Path


def build_executable():
    """Build standalone executable using PyInstaller."""
    print("Building Whisper STT executable...")
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",           # Single executable file
        "--windowed",          # No console window
        "--name", "whisper-stt",
        "--add-data", "requirements.txt;.",
        "--hidden-import", "pynput.keyboard._win32",
        "--hidden-import", "pynput.mouse._win32",
        "--hidden-import", "pystray._win32",
        "--collect-all", "faster_whisper",
        "--collect-all", "sounddevice",
        "--clean",
        "main.py"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode == 0:
        print("")
        print("Build successful!")
        print(f"Executable location: {Path('dist/whisper-stt.exe').absolute()}")
    else:
        print("")
        print("Build failed!")
        sys.exit(1)


def create_spec():
    """Create PyInstaller spec file for advanced builds."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pystray._win32',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='whisper-stt',
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
    icon=None,
)
'''
    
    spec_path = Path('whisper-stt.spec')
    spec_path.write_text(spec_content)
    print(f"Created spec file: {spec_path}")


if __name__ == "__main__":
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("❌ PyInstaller not installed. Run: pip install pyinstaller")
        sys.exit(1)
    
    build_executable()
