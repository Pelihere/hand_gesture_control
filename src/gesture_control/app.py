from __future__ import annotations
import argparse
import logging
import os
import sys
from pathlib import Path
from gesture_control.config.settings import load_settings, config_dir


def setup_logging():
    log_dir = config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_dir / "application.log", encoding="utf-8")]
    if sys.stderr is not None:  # windowed PyInstaller builds have no stderr
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def run_check() -> int:
    """Dependency check that works from source and from the packaged exe (`GestureDesktopControl.exe --check`).

    It does not open the webcam or touch the desktop. It proves that the exact MediaPipe API this
    app uses (`mp.solutions.hands`) exists AND that its model files were packaged, by running the
    hand tracker once on a blank frame. The report is written to <config dir>/logs/check.txt.
    """
    lines: list[str] = []
    failed = False

    def record(ok: bool, text: str) -> None:
        nonlocal failed
        failed = failed or not ok
        lines.append(("[OK]   " if ok else "[FAIL] ") + text)

    record(sys.version_info[:2] in ((3, 11), (3, 12)), f"Python {sys.version.split()[0]} (supported: 3.11-3.12)")
    try:
        import numpy as np
        import cv2
        record(True, f"numpy {np.__version__}, opencv {cv2.__version__}")
        import mediapipe as mp
        where = getattr(mp, "__file__", "?")
        if not hasattr(mp, "solutions"):
            record(False, f"mediapipe {mp.__version__} at {where} has NO 'solutions' API "
                          "(need mediapipe==0.10.21; also check for a file/folder named 'mediapipe' shadowing it)")
        else:
            record(True, f"mediapipe {mp.__version__} at {where}")
            hands = mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=1, model_complexity=0)
            try:
                hands.process(np.zeros((240, 320, 3), dtype=np.uint8))
            finally:
                hands.close()
            record(True, "MediaPipe Hands tracker loaded its model and processed a frame")
    except Exception as exc:
        record(False, f"vision stack: {type(exc).__name__}: {exc}")
    for name in ("PySide6", "pyautogui", "pynput"):
        try:
            __import__(name)
            record(True, f"import {name}")
        except Exception as exc:
            record(False, f"import {name}: {type(exc).__name__}: {exc}")
    if os.name == "nt":
        for name in ("pycaw.pycaw", "comtypes"):
            try:
                __import__(name)
                record(True, f"import {name} (volume control)")
            except Exception as exc:
                lines.append(f"[WARN] {name} unavailable, volume actions will fail: {type(exc).__name__}: {exc}")
    lines.append("RESULT: " + ("FAIL" if failed else "PASS"))
    report = "\n".join(lines)
    try:
        out = config_dir() / "logs"
        out.mkdir(parents=True, exist_ok=True)
        (out / "check.txt").write_text(report + "\n", encoding="utf-8")
    except OSError:
        pass
    if sys.stdout is not None:
        print(report)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-first hand gesture desktop controller")
    parser.add_argument("--background", action="store_true", help="start hidden in the system tray")
    parser.add_argument("--check", action="store_true", help="verify dependencies (no camera, no desktop actions) and exit")
    args, _ = parser.parse_known_args()
    if args.check:
        return run_check()
    setup_logging()
    # Imported here so `--check` does not need a display and fails with a readable report, not a traceback.
    from PySide6.QtWidgets import QApplication
    from gesture_control.ui.main_window import MainWindow
    from gesture_control.input.hotkeys import HotkeyListener
    settings = load_settings()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Gesture Desktop Control")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(settings, app)
    hotkeys = HotkeyListener(window.hotkey_toggle_requested.emit, window.hotkey_emergency_requested.emit,
        settings.get("activation_hotkey", "<ctrl>+<alt>+g"), settings.get("emergency_stop_hotkey", "<ctrl>+<alt>+x"))
    window.set_hotkey_status(hotkeys.start(), hotkeys.error or "")
    app.aboutToQuit.connect(hotkeys.stop)
    if settings.get("_recovery_note"):
        window._log_line("Settings file was invalid and was reset to safe defaults: " + str(settings["_recovery_note"]))
    if args.background or settings.get("start_minimized", False): window.hide()
    else: window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
