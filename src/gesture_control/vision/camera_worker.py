from __future__ import annotations

import logging
import time
from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class CameraWorker(QThread):
    frame_ready = Signal(object, object, str)  # RGB frame, list of landmark objects, status
    camera_state = Signal(bool, str)

    def __init__(self, camera_index: int = 0, max_hands: int = 2, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.max_hands = max_hands
        self._stop_requested = False
        self._state_reported = False
        # Backpressure: the UI thread must finish a frame before the next one is queued. Without
        # this the worker (no sleep) floods Qt's event queue with full-size frames, latency grows
        # without bound and every gesture/action arrives long after the hand moved.
        self._frame_pending = False
        self._pending_since = 0.0

    def frame_consumed(self):
        """Called by the UI thread when it has finished handling the last frame."""
        self._frame_pending = False

    def stop(self):
        self._stop_requested = True
        self.requestInterruption()
        if self.isRunning():
            self.wait(3000)

    def _report_state(self, available: bool, message: str) -> None:
        self._state_reported = True
        log.info("Camera state available=%s: %s", available, message)
        self.camera_state.emit(available, message)

    def _open_camera(self, cv2):
        # The same index can behave differently across Windows capture APIs.
        backends = (
            ("DirectShow", cv2.CAP_DSHOW),
            ("Media Foundation", cv2.CAP_MSMF),
            ("Default backend", cv2.CAP_ANY),
        )
        errors = []
        for name, backend in backends:
            if self._stop_requested or self.isInterruptionRequested():
                return None, errors
            cap = None
            try:
                log.info("Trying camera index %s with %s", self.camera_index, name)
                cap = cv2.VideoCapture(self.camera_index, backend)
                if cap.isOpened():
                    # Opening a device is not enough: make sure a frame can actually be read.
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        log.info("Camera opened using %s", name)
                        return cap, errors
                    errors.append(f"{name}: device opened but no frame was returned")
                else:
                    errors.append(f"{name}: could not open index {self.camera_index}")
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        return None, errors

    def run(self):
        cap = None
        hands = None
        failed = False
        try:
            import cv2
            import mediapipe as mp

            if not hasattr(mp, "solutions"):
                # Newer MediaPipe releases (e.g. 0.10.32) no longer expose the legacy `mp.solutions` API this app uses.
                raise RuntimeError(
                    f"The installed mediapipe {getattr(mp, '__version__', '?')} "
                    f"({getattr(mp, '__file__', 'unknown location')}) has no 'solutions' API. "
                    "This app needs mediapipe==0.10.21 on Python 3.11. Re-run BUILD_PORTABLE.bat, or "
                    "check that no file or folder named 'mediapipe' sits next to the app and shadows the package."
                )

            cap, backend_errors = self._open_camera(cv2)
            if cap is None:
                if self._stop_requested or self.isInterruptionRequested():
                    return
                failed = True
                self._report_state(
                    False,
                    f"Cannot read camera index {self.camera_index}. " + " | ".join(backend_errors),
                )
                return

            # Initialize MediaPipe before reporting ready, so initialization failures are visible.
            try:
                hands = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=self.max_hands,
                    model_complexity=0,
                    min_detection_confidence=0.58,
                    min_tracking_confidence=0.52,
                )
            except Exception as exc:
                failed = True
                self._report_state(
                    False,
                    f"Camera opened, but hand tracking failed: {type(exc).__name__}: {exc}",
                )
                log.exception("MediaPipe hand tracker initialization failed")
                return

            self._report_state(True, "Camera connected; hand tracker ready")
            while not self._stop_requested and not self.isInterruptionRequested():
                ok, frame = cap.read()
                if not ok or frame is None:
                    failed = True
                    self._report_state(
                        False,
                        "Camera opened but frame reading failed. Close other camera apps and retry.",
                    )
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)
                all_landmarks = result.multi_hand_landmarks or []
                now = time.monotonic()
                # Drop the frame if the UI is still busy (but never stall for more than 1 s).
                if self._frame_pending and now - self._pending_since < 1.0:
                    self.msleep(1)
                    continue
                preview = rgb.copy()
                for hand in all_landmarks:
                    mp.solutions.drawing_utils.draw_landmarks(
                        preview, hand, mp.solutions.hands.HAND_CONNECTIONS
                    )
                self._frame_pending = True
                self._pending_since = now
                self.frame_ready.emit(preview, all_landmarks, f"Hands: {len(all_landmarks)}")
                self.msleep(1)

        except Exception as exc:
            failed = True
            self._report_state(False, f"Camera pipeline error: {type(exc).__name__}: {exc}")
            log.exception("Camera worker failed")
        finally:
            if hands is not None:
                try:
                    hands.close()
                except Exception:
                    log.debug("Error closing MediaPipe tracker", exc_info=True)
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    log.debug("Error releasing camera", exc_info=True)
            # Do not overwrite the real failure with the misleading generic 'Camera stopped'.
            if not failed and not self._state_reported:
                self._report_state(False, "Camera stopped")
            elif not failed and (self._stop_requested or self.isInterruptionRequested()):
                self._report_state(False, "Camera stopped")
