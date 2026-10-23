from gesture_control.actions.executor import ActionExecutor
from gesture_control.core import controller as ctl
from gesture_control.core.controller import GestureController
from gesture_control.gestures.recognizer import GestureEvent
from fakes import FakePyAutoGUI


def make_controller(dry_run=True, mappings=None, fake=None):
    messages, lines = [], []
    settings = {"dry_run": dry_run, "cursor_mode": "absolute", "smoothing": 0.35,
                "mappings": mappings or {"pinch": {"action": "left_click", "enabled": True},
                                         "point": {"action": "pointer_move", "enabled": True}}}
    executor = ActionExecutor(dry_run=dry_run, reporter=messages.append)
    if fake is not None:
        executor._pyautogui = fake
    controller = GestureController(settings, executor, event_reporter=lines.append)
    return controller, messages, lines


def armed(controller):
    controller.camera_available(True)
    assert controller.toggle()


def test_events_do_nothing_while_control_off():
    controller, messages, _ = make_controller()
    controller.camera_available(True)
    controller.handle_event(GestureEvent("pinch", 1.0), None)
    assert not any("left_click" in message for message in messages)


def test_camera_loss_disarms_and_reconnect_does_not_rearm():
    controller, messages, _ = make_controller()
    controller.camera_available(True)
    assert controller.toggle()
    controller.camera_available(False)
    controller.camera_available(True)
    before = len(messages)
    controller.handle_event(GestureEvent("pinch", 2.0), None)
    assert len(messages) == before
    assert not controller.gate.can_execute


def test_dry_run_reports_but_does_not_execute_action():
    controller, messages, _ = make_controller()
    armed(controller)
    outcome = controller.handle_event(GestureEvent("pinch", 1.0), None)
    assert any(message == "DRY RUN: left_click" for message in messages)
    assert outcome.stage == ctl.DRY_RUN


def test_emergency_stop_latches():
    controller, messages, _ = make_controller()
    controller.camera_available(True)
    assert controller.toggle()
    controller.emergency_stop()
    assert not controller.toggle()
    controller.reset_emergency()
    assert not controller.gate.can_execute


# ------------------------------------------------ the five pipeline states, each distinct
def test_stage2_unmapped_gesture_is_reported_not_dropped():
    controller, _, lines = make_controller()
    armed(controller)
    outcome = controller.handle_event(GestureEvent("fist", 1.0), None)
    assert outcome.stage == ctl.UNMAPPED
    assert any("fist" in line and "NOT MAPPED" in line for line in lines)


def test_stage2_disabled_mapping_and_none_action_are_explained():
    controller, _, lines = make_controller(mappings={"pinch": {"action": "left_click", "enabled": False},
                                                     "peace": {"action": "none", "enabled": True}})
    armed(controller)
    assert controller.handle_event(GestureEvent("pinch", 1.0), None).stage == ctl.UNMAPPED
    assert controller.handle_event(GestureEvent("peace", 2.0), None).stage == ctl.UNMAPPED
    assert any("disabled" in line for line in lines)
    assert any("'none'" in line for line in lines)


def test_stage3_blocked_when_control_off_says_why():
    controller, messages, lines = make_controller()
    controller.camera_available(True)
    outcome = controller.handle_event(GestureEvent("pinch", 1.0), None)
    assert outcome.stage == ctl.BLOCKED and "control is OFF" in outcome.detail
    assert any("BLOCKED" in line and "Activate" in line for line in lines)
    assert messages == []  # nothing reached the executor


def test_stage3_blocked_reasons_camera_and_emergency():
    controller, _, _ = make_controller()
    assert "camera" in controller.handle_event(GestureEvent("pinch", 1.0), None).detail
    armed(controller)
    controller.emergency_stop()
    assert "emergency" in controller.handle_event(GestureEvent("pinch", 2.0), None).detail


def test_stage3_blocked_when_gesture_kind_does_not_match_action():
    controller, _, lines = make_controller(mappings={"point": {"action": "left_click", "enabled": True},
                                                     "pinch": {"action": "pointer_move", "enabled": True}})
    armed(controller)
    point = controller.handle_event(GestureEvent("point", 1.0, continuous=True), (0.5, 0.5))
    pinch = controller.handle_event(GestureEvent("pinch", 2.0), (0.5, 0.5))
    assert point.stage == ctl.BLOCKED and "continuous" in point.detail
    assert pinch.stage == ctl.BLOCKED and "pointer_move" in pinch.detail
    assert len(lines) == 2


def test_stage4_failed_action_is_not_reported_as_executed():
    controller, messages, lines = make_controller(dry_run=False, fake=FakePyAutoGUI(raise_on="click"))
    armed(controller)
    outcome = controller.handle_event(GestureEvent("pinch", 1.0), None)
    assert outcome.stage == ctl.FAILED
    assert any("FAILED" in line and "click blocked" in line for line in lines)
    assert not any("EXECUTED" in line for line in lines)


def test_stage5_live_action_reaches_backend_and_is_reported_executed():
    fake = FakePyAutoGUI()
    controller, _, lines = make_controller(dry_run=False, fake=fake)
    armed(controller)
    outcome = controller.handle_event(GestureEvent("pinch", 1.0), None)
    assert outcome.stage == ctl.EXECUTED
    assert ("click", "left") in fake.calls
    assert any("EXECUTED" in line for line in lines)


def test_pointer_motion_moves_cursor_live_without_flooding_the_log():
    fake = FakePyAutoGUI()
    controller, _, lines = make_controller(dry_run=False, fake=fake)
    armed(controller)
    for i in range(30):
        controller.handle_event(GestureEvent("point", float(i), continuous=True), (0.5, 0.5))
    assert sum(1 for c in fake.calls if c[0] == "moveTo") == 30
    assert lines == []


def test_blocked_pointer_motion_is_reported_but_throttled():
    controller, _, lines = make_controller()
    controller.camera_available(True)  # control still OFF
    for i in range(50):
        controller.handle_event(GestureEvent("point", float(i), continuous=True), (0.5, 0.5))
    assert len(lines) == 1 and "BLOCKED" in lines[0]


def test_disarm_helper_turns_control_off_without_latching_emergency():
    controller, _, _ = make_controller()
    armed(controller)
    controller.disarm("Dry-run mode changed")
    assert not controller.gate.enabled
    assert not controller.gate.emergency_stopped
    assert controller.toggle()  # can be re-armed explicitly
