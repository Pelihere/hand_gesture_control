from __future__ import annotations
import logging
import platform
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)

# Outcome states of one action request. They are deliberately distinct so the UI can never
# report "executed" for something that was simulated, blocked or failed.
EXECUTED = "executed"   # a real desktop action was performed
DRY_RUN = "dry_run"     # simulated only; nothing happened on the desktop
FAILED = "failed"       # the backend raised an error; nothing (or only part) happened
BLOCKED = "blocked"     # rejected before reaching any backend (e.g. not on the allow-list)
NOOP = "noop"           # mapped to "none"


@dataclass(frozen=True)
class ActionResult:
    action: str
    status: str
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (EXECUTED, DRY_RUN, NOOP)

    def __bool__(self) -> bool:  # keeps `if executor.execute(...)` style callers working
        return self.ok


class ActionExecutor:
    """Allow-listed desktop actions. No shell execution or arbitrary config-driven code."""
    ALLOWED = {"none", "pointer_move", "left_click", "right_click", "double_click", "scroll_up",
               "scroll_down", "volume_up", "volume_down", "escape", "enter", "space"}

    def __init__(self, dry_run: bool = True, reporter: Callable[[str], None] | None = None):
        self.dry_run = dry_run
        self.reporter = reporter or (lambda _: None)
        self._pyautogui = None
        self._volume = None
        self._last_point: tuple[int, int] | None = None
        self._last_pointer_report = 0.0
        self._last_error_report: dict[str, float] = {}

    def _report(self, text: str) -> None:
        log.info(text)
        self.reporter(text)

    # ------------------------------------------------------------------ backends
    def _load_pyautogui(self):
        if self._pyautogui is None:
            import pyautogui
            pyautogui.FAILSAFE = True
            # Default PAUSE adds a sleep after every call; pointer moves happen every frame.
            pyautogui.PAUSE = 0
            self._pyautogui = pyautogui
        return self._pyautogui

    def _volume_endpoint(self):
        if platform.system() != "Windows":
            raise RuntimeError("System volume control requires Windows")
        if self._volume is None:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            device = AudioUtilities.GetSpeakers()
            # Newer pycaw wraps the device (AudioDevice) and exposes the raw COM object as `_dev`.
            raw = getattr(device, "_dev", device)
            interface = raw.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._volume = cast(interface, POINTER(IAudioEndpointVolume))
        return self._volume

    def _adjust_volume(self, delta: int) -> float:
        endpoint = self._volume_endpoint()
        current = endpoint.GetMasterVolumeLevelScalar()
        target = max(0.0, min(1.0, current + delta / 100.0))
        endpoint.SetMasterVolumeLevelScalar(target, None)
        return target

    # ------------------------------------------------------------------ main entry
    def execute_detailed(self, action: str, *, point: tuple[int, int] | None = None) -> ActionResult:
        """Run one allow-listed action and return exactly what happened."""
        if action not in self.ALLOWED:
            result = ActionResult(action, BLOCKED, f"unknown action '{action}' is not on the allow-list")
            self._report(f"BLOCKED unknown action: {action}")
            return result
        if action == "none":
            return ActionResult(action, NOOP)
        if self.dry_run:
            # Pointer events are continuous; throttle log output to avoid flooding the UI/log.
            now = time.monotonic()
            if action != "pointer_move" or now - self._last_pointer_report >= 0.5:
                self._report(f"DRY RUN: {action}" + (f" at {point}" if point else ""))
                if action == "pointer_move":
                    self._last_pointer_report = now
            return ActionResult(action, DRY_RUN, "Dry-run is ON: nothing was sent to the desktop")
        try:
            detail = self._perform(action, point)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            result = ActionResult(action, FAILED, message)
            # Failures can repeat every frame (pointer_move); report each distinct failure at most every 2 s.
            now = time.monotonic()
            if now - self._last_error_report.get(action, -999.0) >= 2.0:
                self._last_error_report[action] = now
                self._report(f"ACTION ERROR ({action}): {message}")
            log.debug("Action %s failed", action, exc_info=True)
            return result
        if action != "pointer_move":  # pointer_move is continuous; logging each one would flood the log
            self._report(f"EXECUTED: {action}" + (f" ({detail})" if detail else ""))
        return ActionResult(action, EXECUTED, detail)

    def execute(self, action: str, *, point: tuple[int, int] | None = None) -> ActionResult:
        return self.execute_detailed(action, point=point)

    def _perform(self, action: str, point: tuple[int, int] | None) -> str:
        if action in ("volume_up", "volume_down"):
            level = self._adjust_volume(2 if action == "volume_up" else -2)
            return f"volume now {level:.0%}"
        p = self._load_pyautogui()
        if action == "pointer_move":
            if point:
                p.moveTo(point[0], point[1], duration=0)
        elif action == "left_click":
            p.click(button="left")
        elif action == "right_click":
            p.click(button="right")
        elif action == "double_click":
            p.doubleClick()
        elif action == "scroll_up":
            p.scroll(3)
        elif action == "scroll_down":
            p.scroll(-3)
        elif action in ("escape", "enter", "space"):
            p.press({"escape": "esc", "enter": "enter", "space": "space"}[action])
        return ""

    # ------------------------------------------------------------------ self-test
    def self_test_pointer(self) -> ActionResult:
        """Move the cursor 40 px and back. Never clicks or types. Independent of webcam/recognizer."""
        if self.dry_run:
            return ActionResult("self_test_pointer", DRY_RUN,
                                "Dry-run is ON: nothing was moved. Uncheck Dry-run to test the real cursor.")
        try:
            p = self._load_pyautogui()
            width, height = p.size()
            x0, y0 = p.position()
            # Step toward the screen centre so the test never touches a fail-safe corner.
            dx = 40 if x0 < width // 2 else -40
            dy = 40 if y0 < height // 2 else -40
            p.moveTo(x0 + dx, y0 + dy, duration=0)
            time.sleep(0.15)
            x1, y1 = p.position()
            p.moveTo(x0, y0, duration=0)
        except Exception as exc:
            return ActionResult("self_test_pointer", FAILED, f"{type(exc).__name__}: {exc}")
        if (x1, y1) == (x0, y0):
            return ActionResult("self_test_pointer", FAILED,
                                "pyautogui ran without error but the cursor did not move "
                                "(blocked by another app, UAC window or a different DPI scale?)")
        return ActionResult("self_test_pointer", EXECUTED, f"cursor moved ({x0},{y0}) -> ({x1},{y1}) and back")

    def self_test_volume(self) -> ActionResult:
        """Raise the master volume by 2 % then restore it, so the net change is zero."""
        if self.dry_run:
            return ActionResult("self_test_volume", DRY_RUN,
                                "Dry-run is ON: volume was not touched. Uncheck Dry-run to test real volume.")
        try:
            before = self._volume_endpoint().GetMasterVolumeLevelScalar()
            self._adjust_volume(2 if before <= 0.97 else -2)
            time.sleep(0.15)
            after = self._volume_endpoint().GetMasterVolumeLevelScalar()
            self._volume_endpoint().SetMasterVolumeLevelScalar(before, None)
        except Exception as exc:
            return ActionResult("self_test_volume", FAILED, f"{type(exc).__name__}: {exc}")
        if abs(after - before) < 0.001:
            return ActionResult("self_test_volume", FAILED, "volume API returned no error but the level did not change")
        return ActionResult("self_test_volume", EXECUTED,
                            f"volume {before:.0%} -> {after:.0%}, then restored to {before:.0%}")

    def release_all(self) -> None:
        """Best-effort release of potentially held inputs during shutdown or camera loss."""
        if self._pyautogui is not None:
            try:
                self._pyautogui.mouseUp(button="left")
                self._pyautogui.mouseUp(button="right")
                self._pyautogui.keyUp("ctrl")
                self._pyautogui.keyUp("alt")
                self._pyautogui.keyUp("shift")
            except Exception:
                log.exception("Failed to release input state")
