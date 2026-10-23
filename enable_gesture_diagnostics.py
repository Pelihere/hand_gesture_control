from __future__ import annotations

"""Add temporary diagnostic logging to Gesture Desktop Control source files.

Run from the project root:
    python enable_gesture_diagnostics.py
The script makes .diagnostic-backup copies before changing any source file.
"""

from pathlib import Path
import shutil
import sys

PATCHES: dict[str, list[tuple[str, str]]] = {
    "src/gesture_control/gestures/recognizer.py": [
        (
            "import time\nfrom typing import Any\n",
            "import time\nimport logging\nfrom typing import Any\n\nlog = logging.getLogger(__name__)\n",
        ),
        (
            "        thumb_index_dist = _dist(lm[4], lm[8])\n        pinch = thumb_index_dist < 0.055\n",
            "        thumb_index_dist = _dist(lm[4], lm[8])\n        pinch = thumb_index_dist < 0.055\n"
            "        # Log only near the pinch threshold or when the pinch state changes, to avoid flooding the log.\n"
            "        if thumb_index_dist < 0.12 or pinch != self._pinch_was_down:\n"
            "            log.info(\"PINCH_CHECK distance=%.4f threshold=0.055 detected=%s previous=%s\",\n"
            "                     thumb_index_dist, pinch, self._pinch_was_down)\n",
        ),
        (
            "        return events\n",
            "        for event in events:\n"
            "            log.info(\"GESTURE_DETECTED name=%s continuous=%s\", event.name, event.continuous)\n"
            "        return events\n",
        ),
    ],
    "src/gesture_control/core/controller.py": [
        (
            "from __future__ import annotations\nfrom typing import Any, Callable\n",
            "from __future__ import annotations\nimport logging\nfrom typing import Any, Callable\n\nlog = logging.getLogger(__name__)\n",
        ),
        (
            "        mapping = self.settings.get(\"mappings\", {}).get(event.name)\n        if not mapping or not mapping.get(\"enabled\", True):\n            return\n        action = mapping.get(\"action\", \"none\")\n",
            "        mapping = self.settings.get(\"mappings\", {}).get(event.name)\n"
            "        log.info(\"EVENT_RECEIVED name=%s continuous=%s gate_enabled=%s can_execute=%s mapping=%r\",\n"
            "                 event.name, event.continuous, self.gate.enabled, self.gate.can_execute, mapping)\n"
            "        if not mapping or not mapping.get(\"enabled\", True):\n"
            "            log.warning(\"EVENT_REJECTED name=%s reason=mapping_missing_or_disabled mapping=%r\", event.name, mapping)\n"
            "            return\n"
            "        action = mapping.get(\"action\", \"none\")\n"
            "        log.info(\"ACTION_MAPPED gesture=%s action=%s\", event.name, action)\n",
        ),
        (
            "            if not self.gate.can_execute or not event.continuous:\n                return\n            if normalized_point is None:\n                return\n",
            "            if not self.gate.can_execute or not event.continuous:\n"
            "                log.warning(\"EVENT_REJECTED name=%s reason=pointer_gate_or_not_continuous can_execute=%s continuous=%s\", event.name, self.gate.can_execute, event.continuous)\n"
            "                return\n"
            "            if normalized_point is None:\n"
            "                log.warning(\"EVENT_REJECTED name=%s reason=missing_normalized_point\", event.name)\n"
            "                return\n",
        ),
        (
            "        if not self.gate.can_execute:\n            return\n        if event.continuous:\n            return\n        self.executor.execute(action)\n",
            "        if not self.gate.can_execute:\n"
            "            log.warning(\"EVENT_REJECTED name=%s reason=gate_disarmed\", event.name)\n"
            "            return\n"
            "        if event.continuous:\n"
            "            log.info(\"EVENT_IGNORED name=%s reason=continuous_non_pointer_action\", event.name)\n"
            "            return\n"
            "        log.info(\"ACTION_REQUEST action=%s dry_run=%s\", action, self.executor.dry_run)\n"
            "        result = self.executor.execute(action)\n"
            "        log.info(\"ACTION_RESULT action=%s result=%s\", action, result)\n",
        ),
    ],
    "src/gesture_control/actions/executor.py": [
        (
            "    def execute(self, action: str, *, point: tuple[int, int] | None = None) -> bool:\n        if action not in self.ALLOWED:\n",
            "    def execute(self, action: str, *, point: tuple[int, int] | None = None) -> bool:\n"
            "        log.info(\"EXECUTOR_REQUEST action=%s dry_run=%s point=%r\", action, self.dry_run, point)\n"
            "        if action not in self.ALLOWED:\n",
        ),
        (
            "        except Exception as exc:\n            self._report(f\"ACTION ERROR ({action}): {type(exc).__name__}: {exc}\")\n            return False\n",
            "        except Exception as exc:\n"
            "            log.exception(\"ACTION_EXCEPTION action=%s\", action)\n"
            "            self._report(f\"ACTION ERROR ({action}): {type(exc).__name__}: {exc}\")\n"
            "            return False\n",
        ),
    ],
    "src/gesture_control/config/settings.py": [
        (
            "import json\nimport os\nfrom pathlib import Path\n",
            "import json\nimport os\nimport logging\nfrom pathlib import Path\n\nlog = logging.getLogger(__name__)\n",
        ),
        (
            "def load_settings(path: Path | None = None) -> dict[str, Any]:\n    path = path or config_path()\n    if not path.exists():\n        save_settings(DEFAULT_CONFIG, path)\n        return validate_settings(DEFAULT_CONFIG)\n    try:\n        return validate_settings(json.loads(path.read_text(encoding=\"utf-8\")))\n",
            "def load_settings(path: Path | None = None) -> dict[str, Any]:\n"
            "    path = path or config_path()\n"
            "    log.info(\"SETTINGS_PATH path=%s exists=%s\", path, path.exists())\n"
            "    if not path.exists():\n"
            "        save_settings(DEFAULT_CONFIG, path)\n"
            "        cfg = validate_settings(DEFAULT_CONFIG)\n"
            "        log.info(\"SETTINGS_EFFECTIVE dry_run=%s pinch=%r\", cfg.get(\"dry_run\"), cfg.get(\"mappings\", {}).get(\"pinch\"))\n"
            "        return cfg\n"
            "    try:\n"
            "        cfg = validate_settings(json.loads(path.read_text(encoding=\"utf-8\")))\n"
            "        log.info(\"SETTINGS_EFFECTIVE dry_run=%s pinch=%r\", cfg.get(\"dry_run\"), cfg.get(\"mappings\", {}).get(\"pinch\"))\n"
            "        return cfg\n",
        ),
    ],
}


def main() -> int:
    root = Path.cwd()
    if not (root / "src/gesture_control").is_dir():
        print("ERROR: Run this script from the project root (the folder containing src/gesture_control).")
        print(f"Current folder: {root}")
        return 2

    backup_root = root / ".diagnostic-backup"
    changed: list[str] = []
    errors: list[str] = []

    for relative, replacements in PATCHES.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing file: {relative}")
            continue
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in replacements:
            count = updated.count(old)
            if count != 1:
                errors.append(f"{relative}: expected one match for a patch block, found {count}. No changes made to this file.")
                updated = original
                break
            updated = updated.replace(old, new, 1)
        else:
            if updated != original:
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copy2(path, backup)
                path.write_text(updated, encoding="utf-8", newline="\n")
                changed.append(relative)

    if errors:
        print("Some patches could not be applied:")
        for error in errors:
            print(f"  - {error}")
    if changed:
        print("Diagnostic logging enabled in:")
        for name in changed:
            print(f"  - {name}")
        print("\nBackups are in .diagnostic-backup\\")
        print("Run the app from this project using your usual Python 3.11 environment.")
        print("Log file: %LOCALAPPDATA%\\GestureDesktopControl\\logs\\application.log")
        print("Reproduce the problem, then inspect the last 100 lines with:")
        print('  Get-Content "$env:LOCALAPPDATA\\GestureDesktopControl\\logs\\application.log" -Tail 100')
    else:
        print("No source files were changed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
