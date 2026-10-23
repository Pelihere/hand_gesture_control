"""Offline self-test: checks Python, dependencies, project imports, config, and safety invariants.
Does not open the webcam or execute desktop actions.
Run: python scripts/self_test.py
"""
from __future__ import annotations
import importlib
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["numpy", "cv2", "mediapipe", "PySide6", "pyautogui", "pynput", "pytest"]
OPTIONAL = ["pycaw", "comtypes"]
errors = 0
print("Gesture Desktop Control · self-test")
print(f"Python: {sys.version.split()[0]} ({platform.system()} {platform.machine()})")
if not ((3,11) <= sys.version_info[:2] < (3,13)):
    print("[WARN] Supported Python range is 3.11–3.12; current version may be incompatible.")
for name in REQUIRED:
    try:
        mod = importlib.import_module(name)
        if name == "mediapipe" and not hasattr(mod, "solutions"):
            raise AttributeError(f"mediapipe {getattr(mod, '__version__', '?')} at {getattr(mod, '__file__', '?')} "
                                 "has no 'solutions' API (need mediapipe==0.10.21; check for a shadowing 'mediapipe' file/folder)")
        print(f"[OK] {name}: {getattr(mod, '__version__', 'imported')}")
    except Exception as exc:
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        errors += 1
try:
    sys.path.insert(0, str(ROOT / "src"))
    from gesture_control.config.settings import DEFAULT_CONFIG, save_settings, load_settings
    from gesture_control.core.safety import SafetyGate
    from gesture_control.actions.executor import ActionExecutor
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "settings.json"
        save_settings(DEFAULT_CONFIG, path)
        cfg = load_settings(path)
        assert cfg["dry_run"] is True
    gate = SafetyGate(camera_available=True)
    assert gate.arm() and gate.can_execute
    gate.camera_lost(); gate.camera_restored()
    assert not gate.can_execute, "camera restoration must not re-arm control"
    reports = []
    executor = ActionExecutor(dry_run=True, reporter=reports.append)
    assert executor.execute("left_click") and reports and reports[0].startswith("DRY RUN")
    assert not executor.execute("shell")
    print("[OK] config round-trip, safety gate, dry-run and action allow-list")
except Exception as exc:
    print(f"[FAIL] internal smoke tests: {type(exc).__name__}: {exc}")
    errors += 1
for name in OPTIONAL:
    try:
        importlib.import_module(name)
        print(f"[OK] optional Windows volume dependency {name}")
    except Exception:
        print(f"[WARN] optional dependency missing: {name} (needed for real volume control on Windows)")
print("\nNote: camera hardware and global hotkeys require a separate manual check.")
print(f"Result: {'PASS' if errors == 0 else 'FAIL'} ({errors} required check(s) failed)")
raise SystemExit(0 if errors == 0 else 1)
