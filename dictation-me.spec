# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

ctranslate2_datas = collect_data_files("ctranslate2")
ctranslate2_binaries = collect_dynamic_libs("ctranslate2")
faster_whisper_datas = collect_data_files("faster_whisper")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=ctranslate2_binaries,
    datas=ctranslate2_datas + faster_whisper_datas + [("config.py", "."), ("src", "src")],
    hiddenimports=[
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "sounddevice",
        "numpy",
        "keyboard",
        "pyautogui",
        "pyperclip",
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "truststore",
        "_sounddevice_data",
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
    name="dictation-me",
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
    icon="assets\\icon.ico",
)
