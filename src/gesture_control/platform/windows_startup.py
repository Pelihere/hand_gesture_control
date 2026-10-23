from __future__ import annotations
import os
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE = "GestureDesktopControl"

def set_start_with_windows(enabled: bool) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Windows startup registration is only available on Windows."
    try:
        import winreg
        command = f'"{sys.executable}" -m gesture_control --background'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_VALUE, 0, winreg.REG_SZ, command)
            else:
                try: winreg.DeleteValue(key, APP_VALUE)
                except FileNotFoundError: pass
        return True, "Startup setting updated. Gesture control still starts OFF."
    except Exception as exc:
        return False, f"Could not update startup setting: {type(exc).__name__}: {exc}"
