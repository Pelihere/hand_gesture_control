from gesture_control.core.safety import SafetyGate

def test_camera_loss_disarms_and_restore_does_not_rearm():
    gate = SafetyGate(camera_available=True)
    assert gate.arm() is True
    assert gate.can_execute
    gate.camera_lost()
    assert not gate.can_execute
    gate.camera_restored()
    assert not gate.can_execute

def test_cannot_arm_without_camera():
    gate = SafetyGate(camera_available=False)
    assert not gate.arm()

def test_emergency_stop_requires_reset_and_explicit_arm():
    gate = SafetyGate(camera_available=True)
    gate.emergency_stopped = True
    assert not gate.arm()
    gate.reset_emergency()
    assert not gate.can_execute
    assert gate.arm()
