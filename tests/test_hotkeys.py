from types import SimpleNamespace

import pytest

from gesture_control.input.hotkeys import HotkeyMatcher, parse_hotkey, _describe_key


def test_parse_hotkey_letters_and_function_keys():
    assert parse_hotkey("<ctrl>+<alt>+g") == (frozenset({"ctrl", "alt"}), ord("G"))
    assert parse_hotkey("<ctrl>+<shift>+<f5>") == (frozenset({"ctrl", "shift"}), 0x74)


@pytest.mark.parametrize("bad", ["", "<ctrl>+<alt>", "<ctrl>+<alt>+gg", "ctrl++g"])
def test_parse_hotkey_rejects_bad_specs(bad):
    with pytest.raises(ValueError):
        parse_hotkey(bad)


def make_matcher():
    fired = []
    matcher = HotkeyMatcher({"<ctrl>+<alt>+g": lambda: fired.append("toggle"),
                             "<ctrl>+<alt>+x": lambda: fired.append("stop")})
    return matcher, fired


def test_hotkey_fires_once_per_press_despite_autorepeat():
    matcher, fired = make_matcher()
    matcher.press("ctrl", None)
    matcher.press("alt", None)
    for _ in range(5):  # key auto-repeat
        matcher.press(None, ord("G"))
    assert fired == ["toggle"]
    matcher.release(None, ord("G"))
    matcher.press(None, ord("G"))
    assert fired == ["toggle", "toggle"]


def test_hotkey_needs_all_modifiers():
    matcher, fired = make_matcher()
    matcher.press("ctrl", None)
    matcher.press(None, ord("G"))
    assert fired == []


def test_releasing_modifier_disarms_hotkey():
    matcher, fired = make_matcher()
    matcher.press("ctrl", None); matcher.press("alt", None)
    matcher.release("alt", None)
    matcher.press(None, ord("X"))
    assert fired == []


def test_emergency_hotkey():
    matcher, fired = make_matcher()
    matcher.press("ctrl", None); matcher.press("alt", None)
    matcher.press(None, ord("X"))
    assert fired == ["stop"]


def test_matching_uses_virtual_key_not_typed_character():
    # With a Persian layout active, the G key types a Persian letter. pynput reports that as the
    # KeyCode's char, but vk stays 0x47. Matching on vk keeps the hotkey working.
    persian_g = SimpleNamespace(char="ل", vk=0x47)
    assert _describe_key(persian_g) == (None, 0x47)
    matcher, fired = make_matcher()
    matcher.press("ctrl", None); matcher.press("alt", None)
    matcher.press(*_describe_key(persian_g))
    assert fired == ["toggle"]


def test_describe_key_maps_modifier_variants():
    assert _describe_key(SimpleNamespace(name="ctrl_l")) == ("ctrl", None)
    assert _describe_key(SimpleNamespace(name="alt_gr")) == ("alt", None)
    assert _describe_key(SimpleNamespace(name="alt_r")) == ("alt", None)


def test_a_failing_callback_does_not_break_later_hotkeys():
    def boom():
        raise RuntimeError("x")
    fired = []
    matcher = HotkeyMatcher({"<ctrl>+g": boom, "<ctrl>+x": lambda: fired.append("ok")})
    matcher.press("ctrl", None)
    matcher.press(None, ord("G"))
    matcher.press(None, ord("X"))
    assert fired == ["ok"]
