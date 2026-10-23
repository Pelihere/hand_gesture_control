import json
import pytest
from gesture_control.config.settings import DEFAULT_CONFIG, validate_settings, save_settings, load_settings

def test_defaults_are_dry_run_and_known_actions():
    cfg = validate_settings(DEFAULT_CONFIG)
    assert cfg["dry_run"] is True
    assert cfg["mappings"]["point"]["action"] == "pointer_move"

def test_rejects_bad_cursor_mode():
    with pytest.raises(ValueError):
        validate_settings({"cursor_mode":"teleport"})

def test_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(DEFAULT_CONFIG, path)
    cfg = load_settings(path)
    assert cfg["dry_run"] is True
    assert json.loads(path.read_text())["schema_version"] == 1

def test_invalid_json_recovers_to_safe_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{nope", encoding="utf-8")
    cfg = load_settings(path)
    assert cfg["dry_run"] is True
    assert path.exists()
    assert path.with_suffix(".json.invalid").exists()


def test_dry_run_false_survives_save_and_load(tmp_path):
    path = tmp_path / "settings.json"
    cfg = validate_settings({"dry_run": False})
    save_settings(cfg, path)
    assert json.loads(path.read_text())["dry_run"] is False
    assert load_settings(path)["dry_run"] is False


def test_mapping_edits_survive_save_and_load(tmp_path):
    path = tmp_path / "settings.json"
    cfg = validate_settings({"mappings": {"pinch": {"action": "double_click", "enabled": False}}})
    save_settings(cfg, path)
    loaded = load_settings(path)
    assert loaded["mappings"]["pinch"] == {"action": "double_click", "enabled": False}
    assert loaded["mappings"]["point"]["action"] == "pointer_move"  # untouched defaults preserved


def test_unknown_action_is_kept_in_settings_but_blocked_by_executor():
    from gesture_control.actions.executor import ActionExecutor, BLOCKED
    cfg = validate_settings({"mappings": {"pinch": {"action": "format_disk", "enabled": True}}})
    assert cfg["mappings"]["pinch"]["action"] == "format_disk"
    assert ActionExecutor(dry_run=False).execute_detailed("format_disk").status == BLOCKED
