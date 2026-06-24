"""Settings persistence for dictation-me."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
APP_NAME = "dictation-me"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "start_on_login": False,
    "model_size": "base",
    "device": "cpu",
    "compute_type": "int8",
    "hotkey": "ctrl+space",
}


class Settings:
    """Manages application settings with JSON persistence."""

    def __init__(self, path: str = SETTINGS_FILE):
        self._path = os.path.abspath(path)
        self._data: dict[str, Any] = {}
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        """Load settings from disk, using defaults for missing values."""
        with self._lock:
            data = DEFAULTS.copy()
            should_save = False

            if not os.path.exists(self._path):
                should_save = True
            else:
                try:
                    with open(self._path, "r", encoding="utf-8") as handle:
                        raw_data = json.load(handle)
                    if not isinstance(raw_data, dict):
                        raise ValueError("Settings file must contain a JSON object.")
                    data = self._sanitize(raw_data)
                    should_save = data != raw_data
                except (OSError, json.JSONDecodeError, ValueError, TypeError):
                    data = DEFAULTS.copy()
                    should_save = True

            self._data = data

            if should_save:
                self._save_unlocked()

    def save(self) -> None:
        """Persist settings to disk."""
        with self._lock:
            self._save_unlocked()

    @property
    def start_on_login(self) -> bool:
        with self._lock:
            return bool(self._data.get("start_on_login", DEFAULTS["start_on_login"]))

    @start_on_login.setter
    def start_on_login(self, value: bool) -> None:
        self.set_start_on_login(value)

    @property
    def model_size(self) -> str:
        with self._lock:
            return str(self._data.get("model_size", DEFAULTS["model_size"]))

    @model_size.setter
    def model_size(self, value: str) -> None:
        with self._lock:
            self._data["model_size"] = str(value)
            self._save_unlocked()

    @property
    def device(self) -> str:
        with self._lock:
            return str(self._data.get("device", DEFAULTS["device"]))

    @device.setter
    def device(self, value: str) -> None:
        with self._lock:
            self._data["device"] = str(value)
            self._save_unlocked()

    @property
    def compute_type(self) -> str:
        with self._lock:
            return str(self._data.get("compute_type", DEFAULTS["compute_type"]))

    @compute_type.setter
    def compute_type(self, value: str) -> None:
        with self._lock:
            self._data["compute_type"] = str(value)
            self._save_unlocked()

    @property
    def hotkey(self) -> str:
        with self._lock:
            return str(self._data.get("hotkey", DEFAULTS["hotkey"]))

    @hotkey.setter
    def hotkey(self, value: str) -> None:
        with self._lock:
            self._data["hotkey"] = str(value)
            self._save_unlocked()

    def set_start_on_login(self, enabled: bool) -> None:
        """Set start-on-login and update Windows registry."""
        with self._lock:
            enabled = bool(enabled)
            if enabled:
                self._add_to_startup()
            else:
                self._remove_from_startup()

            self._data["start_on_login"] = enabled
            self._save_unlocked()

    def _add_to_startup(self) -> None:
        """Add to Windows startup via registry."""
        if winreg is None:
            return

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, self._startup_command())
        except OSError:
            pass

    def _remove_from_startup(self) -> None:
        """Remove from Windows startup via registry."""
        if winreg is None:
            return

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _sanitize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        data = DEFAULTS.copy()
        data["start_on_login"] = bool(raw_data.get("start_on_login", DEFAULTS["start_on_login"]))

        for key in ("model_size", "device", "compute_type", "hotkey"):
            value = raw_data.get(key, DEFAULTS[key])
            data[key] = str(value) if isinstance(value, str) else DEFAULTS[key]

        return data

    def _save_unlocked(self) -> None:
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        fd = -1
        temp_path = ""
        try:
            fd, temp_path = tempfile.mkstemp(
                dir=directory or None,
                prefix=f"{APP_NAME}-",
                suffix=".tmp",
                text=True,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                json.dump(self._data, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
        except OSError:
            if fd != -1:
                os.close(fd)
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _startup_command(self) -> str:
        executable = os.path.abspath(sys.executable)

        if getattr(sys, "frozen", False):
            return f'"{executable}"'

        if executable.lower().endswith("python.exe"):
            candidate = executable[:-10] + "pythonw.exe"
            if os.path.exists(candidate):
                executable = candidate

        main_path = os.path.join(os.path.dirname(self._path), "main.py")
        return f'"{executable}" "{os.path.abspath(main_path)}"'
