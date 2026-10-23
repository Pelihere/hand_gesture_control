from __future__ import annotations
import json
import logging
import time
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton, QComboBox, QCheckBox,
    QSlider, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QSystemTrayIcon, QMenu,
    QMessageBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QStyle, QPlainTextEdit)
from gesture_control.vision.camera_worker import CameraWorker
from gesture_control.gestures.recognizer import GestureRecognizer, GESTURE_NAMES
from gesture_control.core.controller import GestureController
from gesture_control.actions import executor as ex
from gesture_control.actions.executor import ActionExecutor
from gesture_control.config.settings import save_settings
from gesture_control.platform.windows_startup import set_start_with_windows

log = logging.getLogger(__name__)
GESTURES = list(GESTURE_NAMES)
ACTIONS = ["none", "pointer_move", "left_click", "right_click", "double_click", "scroll_up", "scroll_down", "volume_up", "volume_down", "escape", "enter", "space"]

_STATE_STYLE = {
    "off": "background:#2b2f38;color:#e6e6e6;",
    "dry": "background:#7a5c00;color:#ffffff;",
    "live": "background:#9b1c1c;color:#ffffff;",
    "stop": "background:#9b1c1c;color:#ffffff;",
}


class MainWindow(QMainWindow):
    hotkey_toggle_requested = Signal()
    hotkey_emergency_requested = Signal()
    def __init__(self, settings: dict, app=None):
        super().__init__()
        self.settings = settings
        self.app = app
        self.hotkey_toggle_requested.connect(self._toggle_control)
        self.hotkey_emergency_requested.connect(self.controller_emergency_stop)
        self.worker = None
        self._hand_visible = False
        self._saved_snapshot = ""
        self.recognizer = GestureRecognizer()
        # The executor logs to the application log itself. Everything the user needs to see in the window
        # (executed / dry run / blocked / failed) is reported once, by the controller, via _log_line.
        self.executor = ActionExecutor(dry_run=bool(settings.get("dry_run", True)))
        self.controller = GestureController(settings, self.executor, self._set_status, event_reporter=self._log_line)
        self._build_ui()
        self._build_tray()
        self._apply_startup_setting()
        self._saved_snapshot = self._snapshot()
        self._connect_live_signals()
        self._set_status("Ready. Control is OFF. " + ("Dry-run is ON: actions are only simulated."
                         if self.executor.dry_run else "Dry-run is OFF: actions will be LIVE once activated."))
        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._refresh_state)
        self._state_timer.start(200)
        self._refresh_state()
        self._start_camera()

    # ------------------------------------------------------------------ UI construction
    def _build_ui(self):
        self.setWindowTitle("Gesture Desktop Control")
        self.resize(1050, 820)
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        header = QHBoxLayout()
        self.status = QLabel("Starting…"); self.status.setWordWrap(True)
        self.toggle_btn = QPushButton("Activate / Deactivate  (Ctrl+Alt+G)")
        self.toggle_btn.clicked.connect(self._toggle_control)
        self.stop_btn = QPushButton("EMERGENCY STOP  (Ctrl+Alt+X)")
        self.stop_btn.clicked.connect(self.controller.emergency_stop)
        header.addWidget(self.status, 1); header.addWidget(self.toggle_btn); header.addWidget(self.stop_btn)
        layout.addLayout(header)
        # One always-visible line answering: is the camera up, is control armed, is it live or simulated?
        self.state_label = QLabel("…")
        self.state_label.setMinimumHeight(30)
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.state_label)
        self.hotkey_label = QLabel("")
        self.hotkey_label.setWordWrap(True)
        self.hotkey_label.setVisible(False)
        layout.addWidget(self.hotkey_label)
        main = QHBoxLayout()
        self.preview = QLabel("Camera preview will appear here")
        self.preview.setMinimumSize(640, 420); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#16191f;color:#ddd;border:1px solid #555")
        self.preview.setScaledContents(False)
        main.addWidget(self.preview, 3)
        right = QVBoxLayout()
        camera_group = QGroupBox("Camera and control"); form = QFormLayout(camera_group)
        self.camera_combo = QComboBox(); self.camera_combo.addItems([str(i) for i in range(5)])
        self.camera_combo.setCurrentText(str(self.settings.get("camera_index", 0)))
        form.addRow("Camera index", self.camera_combo)
        self.cursor_combo = QComboBox(); self.cursor_combo.addItems(["absolute", "relative"])
        self.cursor_combo.setCurrentText(self.settings.get("cursor_mode", "absolute")); form.addRow("Cursor mode", self.cursor_combo)
        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal); self.smoothing_slider.setRange(0, 95)
        self.smoothing_slider.setValue(int(round(float(self.settings.get("smoothing", .35))*100))); form.addRow("Smoothing", self.smoothing_slider)
        self.dry_run = QCheckBox("Dry-run (recognize only; no desktop actions)")
        self.dry_run.setChecked(bool(self.settings.get("dry_run", True))); form.addRow(self.dry_run)
        self.startup = QCheckBox("Start with Windows (control remains OFF)")
        self.startup.setChecked(bool(self.settings.get("start_with_windows", False))); form.addRow(self.startup)
        self.max_hands = QSpinBox(); self.max_hands.setRange(1,2); self.max_hands.setValue(int(self.settings.get("max_hands",2))); form.addRow("Hands to track", self.max_hands)
        self.camera_btn = QPushButton("Stop camera")
        self.camera_btn.clicked.connect(self._toggle_camera)
        self.save_btn = QPushButton("Save settings")
        self.save_btn.clicked.connect(self._save_settings)
        self.reset_btn = QPushButton("Reset emergency stop")
        self.reset_btn.clicked.connect(self.controller.reset_emergency)
        test_group = QGroupBox("Action self-test (no webcam, no gestures)")
        test_layout = QVBoxLayout(test_group)
        self.test_pointer_btn = QPushButton("Test cursor: move 40 px and back")
        self.test_pointer_btn.clicked.connect(self._self_test_pointer)
        self.test_volume_btn = QPushButton("Test volume: +2 % then restore")
        self.test_volume_btn.clicked.connect(self._self_test_volume)
        hint = QLabel("Needs Dry-run OFF. Never clicks or types.")
        hint.setWordWrap(True)
        test_layout.addWidget(self.test_pointer_btn); test_layout.addWidget(self.test_volume_btn); test_layout.addWidget(hint)
        right.addWidget(camera_group); right.addWidget(self.camera_btn); right.addWidget(self.save_btn)
        right.addWidget(self.reset_btn); right.addWidget(test_group)
        main.addLayout(right, 2); layout.addLayout(main)
        mapping_group = QGroupBox("Gesture mappings (allow-listed actions only; changes apply immediately, Save keeps them)")
        mapping_layout = QVBoxLayout(mapping_group)
        self.mapping_table = QTableWidget(len(GESTURES), 3)
        self.mapping_table.setHorizontalHeaderLabels(["Gesture", "Action", "Enabled"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, gesture in enumerate(GESTURES):
            self.mapping_table.setItem(row, 0, QTableWidgetItem(gesture))
            combo = QComboBox(); combo.addItems(ACTIONS)
            combo.setCurrentText(self.settings.get("mappings", {}).get(gesture, {}).get("action", "none"))
            self.mapping_table.setCellWidget(row, 1, combo)
            check = QCheckBox(); check.setChecked(self.settings.get("mappings", {}).get(gesture, {}).get("enabled", True))
            check.setToolTip("Enable/disable this gesture mapping")
            self.mapping_table.setCellWidget(row, 2, check)
        self.mapping_table.setMaximumHeight(245)
        mapping_layout.addWidget(self.mapping_table); layout.addWidget(mapping_group)
        log_group = QGroupBox("Event log: every detected gesture and what happened to it (no video is saved)")
        log_layout = QVBoxLayout(log_group)
        self.event_log = QPlainTextEdit(); self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(300); self.event_log.setMinimumHeight(120)
        self.event_log.setPlaceholderText("No events yet. Show a gesture to the camera.")
        log_layout.addWidget(self.event_log); layout.addWidget(log_group)

    def _connect_live_signals(self):
        # Edits to mappings / cursor mode / smoothing must reach the controller immediately; before,
        # they only took effect after "Save settings", so a changed table silently did nothing.
        self.cursor_combo.currentTextChanged.connect(self._apply_live_settings)
        self.smoothing_slider.valueChanged.connect(self._apply_live_settings)
        self.startup.toggled.connect(self._apply_live_settings)
        self.max_hands.valueChanged.connect(self._apply_live_settings)
        self.camera_combo.currentTextChanged.connect(self._apply_live_settings)
        for row in range(len(GESTURES)):
            self.mapping_table.cellWidget(row, 1).currentTextChanged.connect(self._apply_live_settings)
            self.mapping_table.cellWidget(row, 2).toggled.connect(self._apply_live_settings)
        self.dry_run.toggled.connect(self._on_dry_run_toggled)

    # ------------------------------------------------------------------ settings <-> widgets
    def _collect_settings(self) -> dict:
        mappings = {}
        for row, gesture in enumerate(GESTURES):
            mappings[gesture] = {
                "action": self.mapping_table.cellWidget(row, 1).currentText(),
                "enabled": self.mapping_table.cellWidget(row, 2).isChecked(),
            }
        return {
            "camera_index": int(self.camera_combo.currentText()),
            "cursor_mode": self.cursor_combo.currentText(),
            "smoothing": round(self.smoothing_slider.value() / 100, 2),
            "dry_run": self.dry_run.isChecked(),
            "start_with_windows": self.startup.isChecked(),
            "max_hands": self.max_hands.value(),
            "mappings": mappings,
        }

    def _snapshot(self) -> str:
        return json.dumps(self._collect_settings(), sort_keys=True)

    def _apply_live_settings(self, *_):
        self.settings.update(self._collect_settings())
        self.controller.settings = self.settings
        self._refresh_state()

    def _on_dry_run_toggled(self, checked: bool):
        self.executor.dry_run = bool(checked)
        self.settings["dry_run"] = bool(checked)
        # Changing between simulated and real actions must never leave control armed: the user has to
        # press Activate again on purpose.
        self.controller.disarm("Dry-run mode changed - press Activate again")
        self._log_line("Dry-run ON: actions are only simulated." if checked
                       else "Dry-run OFF: actions will be LIVE after you press Activate.")
        self._refresh_state()

    def _save_settings(self):
        try:
            self.settings.update(self._collect_settings())
            self.executor.dry_run = bool(self.settings["dry_run"])
            self.controller.settings = self.settings
            save_settings(self.settings)
        except Exception as exc:
            log.exception("Saving settings failed")
            self._set_status(f"Settings NOT saved: {type(exc).__name__}: {exc}")
            QMessageBox.warning(self, "Settings not saved", f"{type(exc).__name__}: {exc}")
            return
        self._saved_snapshot = self._snapshot()
        ok, message = set_start_with_windows(self.settings["start_with_windows"])
        self._log_line(message)
        self._set_status("Settings saved. " + message)
        self._refresh_state()
        QMessageBox.information(self, "Settings", "Settings saved.\n" + message)

    # ------------------------------------------------------------------ live state display
    def _refresh_state(self):
        gate = self.controller.gate
        if gate.emergency_stopped:
            control, style = "EMERGENCY STOP LATCHED", "stop"
        elif gate.enabled and self.executor.dry_run:
            control, style = "Control ON (DRY RUN: nothing is sent)", "dry"
        elif gate.enabled:
            control, style = "Control ON (LIVE)", "live"
        else:
            control, style = "Control OFF (press Activate)", "off"
        camera = "Camera OK" if gate.camera_available else "Camera NOT available"
        mode = "Mode: DRY RUN" if self.executor.dry_run else "Mode: LIVE"
        if self._hand_visible:
            pose = self.recognizer.current_pose or "no static pose"
            seen = f"Seeing: {pose}" + (" + pinch" if self.recognizer.pinching else "")
        else:
            seen = "Seeing: no hand"
        text = "  |  ".join([camera, control, mode, seen])
        if self._snapshot() != self._saved_snapshot:
            text += "  |  unsaved changes"
        if text != self.state_label.text():
            self.state_label.setText(text)
        sheet = "padding:4px;font-weight:600;" + _STATE_STYLE[style]
        if sheet != self.state_label.styleSheet():
            self.state_label.setStyleSheet(sheet)

    def set_hotkey_status(self, ok: bool, text: str = ""):
        self.hotkey_label.setVisible(not ok)
        if not ok:
            self.hotkey_label.setText("Global hotkeys are NOT working: " + text +
                                      "  The Activate and Emergency Stop buttons still work.")
            self.hotkey_label.setStyleSheet("background:#9b1c1c;color:white;padding:4px;")
            self._log_line("WARNING: global hotkeys unavailable: " + text)

    # ------------------------------------------------------------------ self-test
    def _show_self_test(self, result: ex.ActionResult):
        self._log_line(f"SELF-TEST {result.action}: {result.status.upper()} - {result.message}")
        if result.status == ex.EXECUTED:
            QMessageBox.information(self, "Self-test passed (real action performed)", result.message)
        elif result.status == ex.DRY_RUN:
            QMessageBox.information(self, "Dry run - nothing happened", result.message)
        else:
            QMessageBox.warning(self, "Self-test FAILED", result.message)

    def _self_test_allowed(self) -> bool:
        if self.controller.gate.emergency_stopped:
            QMessageBox.warning(self, "Self-test blocked", "Emergency stop is latched. Reset it first.")
            return False
        return True

    def _self_test_pointer(self):
        if self._self_test_allowed():
            self._show_self_test(self.executor.self_test_pointer())

    def _self_test_volume(self):
        if self._self_test_allowed():
            self._show_self_test(self.executor.self_test_volume())

    # ------------------------------------------------------------------ tray
    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Gesture Desktop Control · control OFF")
        menu = QMenu()
        show_action = QAction("Show window", self); show_action.triggered.connect(self.showNormal); menu.addAction(show_action)
        toggle_action = QAction("Activate / Deactivate", self); toggle_action.triggered.connect(self._toggle_control); menu.addAction(toggle_action)
        stop_action = QAction("Emergency stop", self); stop_action.triggered.connect(self.controller.emergency_stop); menu.addAction(stop_action)
        quit_action = QAction("Quit", self); quit_action.triggered.connect(self._quit); menu.addAction(quit_action)
        self.tray.setContextMenu(menu); self.tray.activated.connect(self._tray_activated); self.tray.show()

    # ------------------------------------------------------------------ camera / frames
    def _start_camera(self):
        if self.worker and self.worker.isRunning(): return
        self.recognizer.reset()
        self.worker = CameraWorker(int(self.camera_combo.currentText()), self.max_hands.value())
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.camera_state.connect(self._on_camera_state)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start(); self.camera_btn.setText("Stop camera")

    def _on_frame(self, rgb, hands, status):
        try:
            # Handle the gestures first, then draw: drawing/scaling the preview is the slow part and
            # must not delay the action the user just asked for.
            now = time.monotonic()
            self._hand_visible = bool(hands)
            if hands:
                # Use first detected hand for primary control; still draw up to two in preview.
                hand = hands[0]
                for event in self.recognizer.process(hand, now):
                    point = (float(hand.landmark[8].x), float(hand.landmark[8].y)) if event.name == "point" else None
                    self.controller.handle_event(event, point)
            else:
                self.recognizer.reset()
            height, width, channels = rgb.shape
            image = QImage(rgb.data, width, height, channels*width, QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(image).scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.preview.setPixmap(pixmap)
        except Exception:
            log.exception("Frame handling failed")
        finally:
            if self.worker is not None:
                self.worker.frame_consumed()

    def _on_camera_state(self, available, message):
        self.controller.camera_available(available)
        if not available:
            self.recognizer.reset()
            self._hand_visible = False
        self._set_status(message)
        if not available:
            self.preview.setText(message)
        self._refresh_state()

    def _on_worker_finished(self):
        # Thread finished must leave the controller disarmed even on unexpected exit.
        if self.controller.gate.enabled:
            self.controller.camera_available(False)

    def _toggle_camera(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop(); self.controller.camera_available(False); self.camera_btn.setText("Start camera")
            self.preview.setText("Camera stopped")
            self._hand_visible = False
        else:
            self._start_camera()

    def controller_emergency_stop(self):
        self.controller.emergency_stop()

    def _toggle_control(self):
        enabled = self.controller.toggle()
        self.tray.setToolTip("Gesture Desktop Control · control " + ("ON" if enabled else "OFF"))
        self._refresh_state()

    def _apply_startup_setting(self):
        # Respect saved preference, but do not silently modify registry on each launch.
        pass

    def _set_status(self, text):
        self.status.setText(text)
        self.tray.setToolTip("Gesture Desktop Control · " + text[:100] if hasattr(self, "tray") else "Gesture Desktop Control")

    def _log_line(self, text):
        log.info(text)
        if hasattr(self, "event_log"):
            self.event_log.appendPlainText(time.strftime("%H:%M:%S ") + text)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal(); self.raise_(); self.activateWindow()

    def closeEvent(self, event):
        # Closing hides to tray but disarms control to avoid invisible desktop actions.
        self.controller.gate.disarm()
        self.executor.release_all()
        self._set_status("Window hidden to tray. Gesture control OFF.")
        event.ignore(); self.hide(); self.tray.showMessage("Gesture Desktop Control", "Running in tray. Gesture control is OFF.")

    def _quit(self):
        self.controller.gate.disarm(); self.executor.release_all()
        if self.worker and self.worker.isRunning(): self.worker.stop()
        if self.app: self.app.quit()
