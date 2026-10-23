from __future__ import annotations
import logging
from typing import Callable

log = logging.getLogger(__name__)

_MODIFIER_ALIASES = {
    "ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl", "control": "ctrl",
    "alt": "alt", "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "cmd": "win", "cmd_l": "win", "cmd_r": "win", "win": "win",
}


def parse_hotkey(spec: str) -> tuple[frozenset[str], int]:
    """Parse '<ctrl>+<alt>+g' into (modifiers, Windows virtual-key code).

    Matching uses the virtual-key code rather than the typed character, so the hotkey keeps
    working when a non-Latin keyboard layout (Persian, Arabic, Russian...) is active.
    """
    modifiers: set[str] = set()
    vk: int | None = None
    for raw in spec.split("+"):
        part = raw.strip().lower().strip("<>")
        if not part:
            raise ValueError(f"empty element in hotkey '{spec}'")
        if part in _MODIFIER_ALIASES:
            modifiers.add(_MODIFIER_ALIASES[part])
        elif len(part) == 1 and (part.isalpha() or part.isdigit()) and part.isascii():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 12:
            vk = 0x70 + int(part[1:]) - 1
        else:
            raise ValueError(f"unsupported key '{raw}' in hotkey '{spec}'")
    if vk is None:
        raise ValueError(f"hotkey '{spec}' has no main key")
    return frozenset(modifiers), vk


class HotkeyMatcher:
    """Pure key-state tracker (no OS dependency, unit-testable)."""

    def __init__(self, bindings: dict[str, Callable[[], None]]):
        self._bindings = [(*parse_hotkey(spec), callback) for spec, callback in bindings.items()]
        self._held: set[str] = set()
        self._fired: set[int] = set()

    def press(self, modifier: str | None, vk: int | None) -> None:
        if modifier:
            self._held.add(modifier)
            return
        if vk is None or vk in self._fired:  # ignore auto-repeat while the key stays down
            return
        for mods, target_vk, callback in self._bindings:
            if vk == target_vk and mods <= self._held:
                self._fired.add(vk)
                try:
                    callback()
                except Exception:
                    log.exception("Hotkey callback failed")
                return

    def release(self, modifier: str | None, vk: int | None) -> None:
        if modifier:
            self._held.discard(modifier)
        elif vk is not None:
            self._fired.discard(vk)

    def reset(self) -> None:
        self._held.clear()
        self._fired.clear()


def _describe_key(key) -> tuple[str | None, int | None]:
    """Translate a pynput key object into (modifier_name, virtual_key)."""
    name = getattr(key, "name", None)
    if name in _MODIFIER_ALIASES:
        return _MODIFIER_ALIASES[name], None
    vk = getattr(key, "vk", None)
    if vk is None:
        value = getattr(key, "value", None)
        vk = getattr(value, "vk", None)
    return None, vk


class HotkeyListener:
    def __init__(self, activate_callback, emergency_callback,
                 activation_hotkey="<ctrl>+<alt>+g", emergency_hotkey="<ctrl>+<alt>+x"):
        self.activate_callback = activate_callback
        self.emergency_callback = emergency_callback
        self.activation_hotkey = activation_hotkey
        self.emergency_hotkey = emergency_hotkey
        self._listener = None
        self.error: str | None = None

    @property
    def running(self) -> bool:
        return self._listener is not None

    def start(self) -> bool:
        """Start listening. Returns False (and sets .error) if hotkeys cannot work; the UI buttons still do."""
        if self._listener is not None:
            return True
        try:
            from pynput import keyboard
            matcher = HotkeyMatcher({self.activation_hotkey: self.activate_callback,
                                     self.emergency_hotkey: self.emergency_callback})

            def on_press(key):
                matcher.press(*_describe_key(key))

            def on_release(key):
                matcher.release(*_describe_key(key))

            self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener.start()
            self.error = None
            return True
        except Exception as exc:
            log.exception("Unable to start global hotkeys")
            self._listener = None
            self.error = f"{type(exc).__name__}: {exc}"
            return False

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
