from unittest import mock

from gesture_control.actions import executor as ex
from gesture_control.actions.executor import ActionExecutor
from fakes import FakePyAutoGUI


def live_executor(fake=None):
    executor = ActionExecutor(dry_run=False)
    executor._pyautogui = fake or FakePyAutoGUI()
    return executor


def test_dry_run_does_not_import_or_execute_desktop_actions():
    seen = []
    executor = ActionExecutor(dry_run=True, reporter=seen.append)
    result = executor.execute("left_click")
    assert result and result.status == ex.DRY_RUN
    assert seen == ["DRY RUN: left_click"]
    assert executor._pyautogui is None  # backend never loaded in dry-run


def test_unknown_action_is_blocked_even_in_dry_run():
    seen = []
    executor = ActionExecutor(dry_run=True, reporter=seen.append)
    result = executor.execute("run_shell_command")
    assert not result and result.status == ex.BLOCKED
    assert "BLOCKED" in seen[0]


def test_live_click_reports_executed_and_reaches_backend():
    fake = FakePyAutoGUI()
    result = live_executor(fake).execute_detailed("left_click")
    assert result.status == ex.EXECUTED
    assert ("click", "left") in fake.calls


def test_backend_exception_is_reported_as_failed_not_executed():
    seen = []
    executor = live_executor(FakePyAutoGUI(raise_on="click"))
    executor.reporter = seen.append
    result = executor.execute_detailed("left_click")
    assert result.status == ex.FAILED and not result
    assert "click blocked" in result.message
    assert any("ACTION ERROR" in line for line in seen)
    assert not any(line.startswith("EXECUTED") for line in seen)


def test_volume_failure_off_windows_is_reported_as_failed():
    with mock.patch("gesture_control.actions.executor.platform.system", return_value="Linux"):
        result = ActionExecutor(dry_run=False).execute_detailed("volume_up")
    assert result.status == ex.FAILED
    assert "Windows" in result.message


def test_none_action_is_noop():
    assert ActionExecutor(dry_run=False).execute_detailed("none").status == ex.NOOP


def test_pointer_move_uses_given_point():
    fake = FakePyAutoGUI()
    result = live_executor(fake).execute_detailed("pointer_move", point=(300, 200))
    assert result.status == ex.EXECUTED
    assert ("moveTo", 300, 200) in fake.calls


# ---------------------------------------------------------------- self-test
def test_self_test_pointer_in_dry_run_is_simulated_and_touches_nothing():
    executor = ActionExecutor(dry_run=True)
    executor._pyautogui = FakePyAutoGUI()
    result = executor.self_test_pointer()
    assert result.status == ex.DRY_RUN
    assert executor._pyautogui.calls == []


def test_self_test_pointer_success_moves_and_restores_without_clicking():
    fake = FakePyAutoGUI()
    result = live_executor(fake).self_test_pointer()
    assert result.status == ex.EXECUTED
    assert [c[0] for c in fake.calls] == ["moveTo", "moveTo"]  # out and back, nothing else
    assert fake.position() == (100, 100)
    assert fake.calls[0][1:] != (100, 100)


def test_self_test_pointer_detects_cursor_that_did_not_move():
    result = live_executor(FakePyAutoGUI(moves=False)).self_test_pointer()
    assert result.status == ex.FAILED
    assert "did not move" in result.message


def test_self_test_pointer_reports_backend_error():
    result = live_executor(FakePyAutoGUI(raise_on="moveTo")).self_test_pointer()
    assert result.status == ex.FAILED
    assert "fail-safe" in result.message


def test_self_test_volume_dry_run_and_failure_off_windows():
    assert ActionExecutor(dry_run=True).self_test_volume().status == ex.DRY_RUN
    with mock.patch("gesture_control.actions.executor.platform.system", return_value="Linux"):
        assert ActionExecutor(dry_run=False).self_test_volume().status == ex.FAILED
