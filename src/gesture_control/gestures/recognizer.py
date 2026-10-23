from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math
import time
from typing import Any

@dataclass(frozen=True)
class GestureEvent:
    name: str
    timestamp: float
    continuous: bool = False


def _dist(a: Any, b: Any) -> float:
    return math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y))


def _finger_up(lm: Any, tip: int, pip: int) -> bool:
    # Image y grows downward; this is a useful webcam heuristic for upright hands.
    return lm[tip].y < lm[pip].y

# Every gesture name the recognizer can emit. Mapping keys in settings/UI must match these exactly.
GESTURE_NAMES = ("point", "pinch", "peace", "open_palm", "fist", "thumbs_up", "swipe_left", "swipe_right")


class GestureRecognizer:
    """Recognizes a small, deliberately conservative gesture set from MediaPipe landmarks."""
    def __init__(self, cooldown: float = 0.65, swipe_window: float = 0.55):
        self.cooldown = cooldown
        self.swipe_window = swipe_window
        self._last_emit: dict[str, float] = {}
        self._pinch_was_down = False
        self._history: deque[tuple[float, float]] = deque(maxlen=20)
        self._last_continuous: str | None = None
        self._pose: str | None = None

    @property
    def current_pose(self) -> str | None:
        """Static pose seen in the last processed frame (for live display only)."""
        return self._pose

    @property
    def pinching(self) -> bool:
        return self._pinch_was_down

    def reset(self) -> None:
        self._history.clear()
        self._pinch_was_down = False
        self._last_continuous = None
        self._pose = None
        self._last_emit.clear()

    def _emit(self, name: str, now: float, continuous: bool = False) -> GestureEvent | None:
        if not continuous and now - self._last_emit.get(name, -999.0) < self.cooldown:
            return None
        if not continuous:
            self._last_emit[name] = now
        return GestureEvent(name, now, continuous)

    def process(self, landmarks: Any, now: float | None = None) -> list[GestureEvent]:
        now = time.monotonic() if now is None else now
        lm = landmarks.landmark if hasattr(landmarks, "landmark") else landmarks
        if len(lm) < 21:
            self.reset()
            return []
        index_up = _finger_up(lm, 8, 6)
        middle_up = _finger_up(lm, 12, 10)
        ring_up = _finger_up(lm, 16, 14)
        pinky_up = _finger_up(lm, 20, 18)
        # Normalize pinch distance by palm length so camera distance and hand size
        # do not change the effective threshold as much.
        thumb_index_dist = _dist(lm[4], lm[8])
        palm_scale = _dist(lm[0], lm[9])  # wrist to middle-finger MCP
        if palm_scale >= 0.02:
            pinch_ratio = thumb_index_dist / palm_scale
            # Hysteresis reduces flicker around the boundary.
            pinch = pinch_ratio < (0.38 if not self._pinch_was_down else 0.52)
        else:
            # Defensive fallback for malformed landmarks.
            pinch = thumb_index_dist < (0.055 if not self._pinch_was_down else 0.075)
        events: list[GestureEvent] = []
        pose = None
        if index_up and not middle_up and not ring_up and not pinky_up:
            pose = "point"
            events.append(GestureEvent("point", now, continuous=True))
        elif index_up and middle_up and not ring_up and not pinky_up:
            pose = "peace"
        elif index_up and middle_up and ring_up and pinky_up:
            pose = "open_palm"
        elif not index_up and not middle_up and not ring_up and not pinky_up:
            pose = "fist"
            # Thumb-up heuristic: four fingers down, thumb tip above thumb IP joint.
            if lm[4].y < lm[3].y - 0.035:
                pose = "thumbs_up"
        # Static poses emit once on entry, not repeatedly while held.
        if pose and pose not in ("point", self._pose):
            event = self._emit(pose, now)
            if event: events.append(event)
        self._pose = pose
        if pinch and not self._pinch_was_down:
            event = self._emit("pinch", now)
            if event: events.append(event)
        self._pinch_was_down = pinch
        wrist_x = float(lm[0].x)
        if pose == "point":
            # Steering the cursor means sweeping the hand across the frame; that must not also
            # register as a swipe (it would change the volume while the user is just pointing).
            self._history.clear()
            return events
        self._history.append((now, wrist_x))
        while self._history and now - self._history[0][0] > self.swipe_window:
            self._history.popleft()
        if len(self._history) >= 5:
            delta = wrist_x - self._history[0][1]
            if delta < -0.24:
                event = self._emit("swipe_left", now)
                if event: events.append(event)
                self._history.clear()
            elif delta > 0.24:
                event = self._emit("swipe_right", now)
                if event: events.append(event)
                self._history.clear()
        return events
