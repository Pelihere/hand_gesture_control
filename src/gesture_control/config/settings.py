from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "GestureDesktopControl"
DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "camera_index": 0,
    "cursor_mode": "absolute",
    "smoothing": 0.35,
    "activation_hotkey": "<ctrl>+<alt>+g",
    "emergency_stop_hotkey": "<ctrl>+<alt>+x",
    "dry_run": True,
    "start_minimized": False,
    "start_with_windows": False,
    "max_hands": 2,
    "mappings": {
        "point": {"action": "pointer_move", "enabled": True},
        "pinch": {"action": "left_click", "enabled": True},
        "peace": {"action": "right_click", "enabled": True},
        "swipe_left": {"action": "volume_down", "enabled": True},
        "swipe_right": {"action": "volume_up", "enabled": True},
        "open_palm": {"action": "none", "enabled": True},
        "fist": {"action": "none", "enabled": True},
        "thumbs_up": {"action": "none", "enabled": True},
    },
}


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".gesture-desktop-control"


def config_path() -> Path:
    return config_dir() / "settings.json"


def validate_settings(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate known settings and merge defaults; reject unknown action names later in executor."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not isinstance(raw, dict):
        raise ValueError("Settings root must be a JSON object")
    for key in ("camera_index", "cursor_mode", "smoothing", "activation_hotkey",
                "emergency_stop_hotkey", "dry_run", "start_minimized", "start_with_windows", "max_hands"):
        if key in raw:
            cfg[key] = raw[key]
    if cfg["cursor_mode"] not in ("absolute", "relative"):
        raise ValueError("cursor_mode must be 'absolute' or 'relative'")
    if not isinstance(cfg["camera_index"], int) or cfg["camera_index"] < 0:
        raise ValueError("camera_index must be a non-negative integer")
    if not isinstance(cfg["smoothing"], (int, float)) or not 0 <= float(cfg["smoothing"]) <= 0.95:
        raise ValueError("smoothing must be between 0 and 0.95")
    if cfg["max_hands"] not in (1, 2):
        raise ValueError("max_hands must be 1 or 2")
    for key in ("dry_run", "start_minimized", "start_with_windows"):
        if not isinstance(cfg[key], bool):
            raise ValueError(f"{key} must be boolean")
    if "mappings" in raw:
        if not isinstance(raw["mappings"], dict):
            raise ValueError("mappings must be an object")
        # Merge by gesture so partial edits don't erase other defaults.
        for gesture, mapping in raw["mappings"].items():
            if gesture not in cfg["mappings"]:
                continue
            if not isinstance(mapping, dict):
                raise ValueError(f"mapping for {gesture} must be an object")
            action = mapping.get("action", cfg["mappings"][gesture]["action"])
            enabled = mapping.get("enabled", cfg["mappings"][gesture]["enabled"])
            if not isinstance(action, str) or not isinstance(enabled, bool):
                raise ValueError(f"invalid mapping for {gesture}")
            cfg["mappings"][gesture] = {"action": action, "enabled": enabled}
    cfg["schema_version"] = 1
    return cfg


def load_settings(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        save_settings(DEFAULT_CONFIG, path)
        return validate_settings(DEFAULT_CONFIG)
    try:
        return validate_settings(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        # Preserve the broken file for user inspection, then recover to safe defaults.
        backup = path.with_suffix(path.suffix + ".invalid")
        try:
            path.replace(backup)
        except OSError:
            pass
        cfg = validate_settings(DEFAULT_CONFIG)
        save_settings(cfg, path)
        cfg["_recovery_note"] = str(exc)
        return cfg


def save_settings(settings: dict[str, Any], path: Path | None = None) -> None:
    path = path or config_path()
    cfg = validate_settings(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    temp.replace(path)
