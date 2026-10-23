from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any, Callable
from gesture_control.core.safety import SafetyGate
from gesture_control.gestures.recognizer import GestureEvent
from gesture_control.actions import executor as ex
from gesture_control.actions.executor import ActionExecutor

# Pipeline stages after a gesture has been *detected* (stage 1, "not detected", is the recognizer's job).
UNMAPPED = "unmapped"    # 2. detected, but no mapping / mapping disabled / action "none"
BLOCKED = "blocked"      # 3. mapped, but safety conditions or a gesture/action mismatch stopped it
FAILED = "failed"        # 4. action attempted, backend raised an error
EXECUTED = "executed"    # 5. real desktop action performed
DRY_RUN = "dry_run"      # 5b. simulated only
IDLE = "idle"            # accepted but nothing to report (pointer priming, "none" action)

POINTER_ACTIONS = {"pointer_move"}


@dataclass(frozen=True)
class EventOutcome:
    gesture: str
    action: str
    stage: str
    detail: str = ""

    def describe(self) -> str:
        arrow = f"{self.gesture} -> {self.action}" if self.action else self.gesture
        label = {UNMAPPED: "NOT MAPPED", BLOCKED: "BLOCKED", FAILED: "FAILED",
                 EXECUTED: "EXECUTED", DRY_RUN: "DRY RUN (nothing sent)", IDLE: "ok"}[self.stage]
        return f"{arrow}: {label}" + (f" - {self.detail}" if self.detail else "")


class GestureController:
    def __init__(self, settings: dict[str, Any], executor: ActionExecutor,
                 status: Callable[[str], None] | None = None,
                 event_reporter: Callable[[str], None] | None = None):
        self.settings = settings
        self.executor = executor
        self.status = status or (lambda _: None)
        # Receives one line per discrete gesture outcome (and throttled lines for blocked pointer motion).
        self.event_reporter = event_reporter or (lambda _: None)
        self.gate = SafetyGate()
        self.last_outcome: EventOutcome | None = None
        self._last_cursor: tuple[float, float] | None = None
        self._smoothed_point: tuple[float, float] | None = None
        self._cursor_position: tuple[float, float] | None = None
        self._last_block_report: dict[str, float] = {}

    # ------------------------------------------------------------------ state
    def _reset_motion(self) -> None:
        self._last_cursor = None
        self._smoothed_point = None
        self._cursor_position = None

    def block_reason(self) -> str | None:
        """Why nothing can run right now, in words the user can act on; None if execution is allowed."""
        if self.gate.emergency_stopped:
            return "emergency stop is latched - press 'Reset emergency stop', then Activate"
        if not self.gate.camera_available:
            return "camera is not available"
        if not self.gate.enabled:
            return "control is OFF - press Activate (Ctrl+Alt+G)"
        return None

    def camera_available(self, available: bool) -> None:
        if available:
            self.gate.camera_restored()
            self.status("Camera available. Gesture control remains OFF until activated.")
        else:
            self.gate.camera_lost()
            self._reset_motion()
            self.executor.release_all()
            self.status("Camera unavailable. Control disarmed for safety.")

    def toggle(self) -> bool:
        if self.gate.enabled:
            self.gate.disarm()
            self._reset_motion()
            self.executor.release_all()
            self.status("Gesture control OFF")
            return False
        if self.gate.arm():
            self._reset_motion()
            self.status("Gesture control ON" + (" (DRY RUN - nothing will be sent to the desktop)"
                                                if self.executor.dry_run else " (LIVE)"))
            return True
        self.status("Cannot activate: " + (self.block_reason() or "unknown reason"))
        return False

    def disarm(self, reason: str) -> None:
        """Turn control OFF without latching the emergency stop (e.g. when the Dry-run mode changes)."""
        was_on = self.gate.enabled
        self.gate.disarm()
        self._reset_motion()
        self.executor.release_all()
        if was_on:
            self.status(f"Gesture control OFF: {reason}")

    def emergency_stop(self) -> None:
        self.gate.disarm(emergency=True)
        self._reset_motion()
        self.executor.release_all()
        self.status("EMERGENCY STOP. Press 'Reset emergency stop', then Activate, to continue.")

    def reset_emergency(self) -> None:
        self.gate.reset_emergency()
        self.status("Emergency stop reset. Control is still OFF.")

    # ------------------------------------------------------------------ events
    def _report_throttled(self, key: str, text: str, interval: float = 3.0) -> None:
        now = time.monotonic()
        if now - self._last_block_report.get(key, -999.0) >= interval:
            self._last_block_report[key] = now
            self.event_reporter(text)

    def _finish(self, outcome: EventOutcome, *, continuous: bool) -> EventOutcome:
        self.last_outcome = outcome
        if outcome.stage == IDLE:
            return outcome
        text = outcome.describe()
        if continuous:
            # Pointer motion arrives every frame: only surface problems, and not more than every 3 s.
            if outcome.stage in (BLOCKED, FAILED, UNMAPPED):
                self._report_throttled(f"{outcome.gesture}:{outcome.stage}:{outcome.detail}", text)
        else:
            self.event_reporter(text)
        return outcome

    def handle_event(self, event: GestureEvent, normalized_point: tuple[float, float] | None = None) -> EventOutcome:
        """Process one detected gesture and return exactly what happened to it."""
        mapping = self.settings.get("mappings", {}).get(event.name)
        if not mapping:
            return self._finish(EventOutcome(event.name, "", UNMAPPED,
                                             "no mapping exists for this gesture name"), continuous=event.continuous)
        if not mapping.get("enabled", True):
            return self._finish(EventOutcome(event.name, mapping.get("action", "none"), UNMAPPED,
                                             "mapping is disabled in settings"), continuous=event.continuous)
        action = mapping.get("action", "none")
        if action == "none":
            return self._finish(EventOutcome(event.name, action, UNMAPPED,
                                             "mapped to 'none' - choose an action in the table"), continuous=event.continuous)

        if action in POINTER_ACTIONS and not event.continuous:
            return self._finish(EventOutcome(event.name, action, BLOCKED,
                                             "pointer_move only works with the continuous 'point' gesture"),
                                continuous=False)
        if action not in POINTER_ACTIONS and event.continuous:
            return self._finish(EventOutcome(event.name, action, BLOCKED,
                                             f"'{event.name}' is a continuous gesture and can only drive "
                                             "pointer_move; map a discrete gesture (e.g. pinch) to this action"),
                                continuous=True)

        reason = self.block_reason()
        if reason:
            return self._finish(EventOutcome(event.name, action, BLOCKED, reason), continuous=event.continuous)

        if action in POINTER_ACTIONS:
            return self._handle_pointer(event, action, normalized_point)

        result = self.executor.execute_detailed(action)
        return self._finish(self._from_result(event.name, result), continuous=False)

    @staticmethod
    def _from_result(gesture: str, result: ex.ActionResult) -> EventOutcome:
        stage = {ex.EXECUTED: EXECUTED, ex.DRY_RUN: DRY_RUN, ex.FAILED: FAILED,
                 ex.BLOCKED: BLOCKED, ex.NOOP: IDLE}[result.status]
        detail = result.message if result.status in (ex.FAILED, ex.BLOCKED, ex.EXECUTED) else ""
        return EventOutcome(gesture, result.action, stage, detail)

    def _handle_pointer(self, event: GestureEvent, action: str,
                        normalized_point: tuple[float, float] | None) -> EventOutcome:
        if normalized_point is None:
            return self._finish(EventOutcome(event.name, action, BLOCKED, "no fingertip position supplied"),
                                continuous=True)
        x, y = normalized_point
        screen_w, screen_h = self._screen_size()
        if self.settings.get("cursor_mode", "absolute") == "relative":
            if self._last_cursor is None:
                self._last_cursor = (x, y)
                try:
                    import pyautogui
                    self._cursor_position = tuple(pyautogui.position())
                except Exception:
                    self._cursor_position = (screen_w // 2, screen_h // 2)
                return self._finish(EventOutcome(event.name, action, IDLE), continuous=True)
            dx, dy = x - self._last_cursor[0], y - self._last_cursor[1]
            self._last_cursor = (x, y)
            sensitivity = 2.2
            cx, cy = self._cursor_position or (screen_w // 2, screen_h // 2)
            target = (int(max(0, min(screen_w - 1, cx + dx * screen_w * sensitivity))),
                      int(max(0, min(screen_h - 1, cy + dy * screen_h * sensitivity))))
        else:
            # Smooth normalized fingertip coordinates before mapping to screen space.
            smoothing = float(self.settings.get("smoothing", 0.35))
            if self._smoothed_point is None:
                self._smoothed_point = (x, y)
            else:
                alpha = max(0.05, 1.0 - smoothing)
                self._smoothed_point = (self._smoothed_point[0] + alpha * (x - self._smoothed_point[0]),
                                        self._smoothed_point[1] + alpha * (y - self._smoothed_point[1]))
            sx, sy = self._smoothed_point
            # Clamp away from the outermost edge to avoid accidental OS hot corners.
            target = (int(max(0.02, min(0.98, sx)) * screen_w), int(max(0.02, min(0.98, sy)) * screen_h))
        self._cursor_position = target
        result = self.executor.execute_detailed(action, point=target)
        outcome = self._from_result(event.name, result)
        if outcome.stage in (EXECUTED, DRY_RUN, IDLE):
            # Moving the cursor 30 times a second is not worth a log line each time.
            self.last_outcome = outcome
            return outcome
        return self._finish(outcome, continuous=True)

    @staticmethod
    def _screen_size() -> tuple[int, int]:
        try:
            import pyautogui
            return pyautogui.size()
        except Exception:
            return (1920, 1080)
