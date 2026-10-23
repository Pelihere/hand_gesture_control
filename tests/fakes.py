"""Test doubles shared by several test modules."""


class FakePyAutoGUI:
    """Stands in for pyautogui so real-mode code paths can be exercised without touching a desktop."""
    def __init__(self, moves=True, raise_on=None):
        self.calls = []
        self.moves = moves
        self.raise_on = raise_on
        self._pos = (100, 100)

    def size(self):
        return (1920, 1080)

    def position(self):
        return self._pos

    def moveTo(self, x, y, duration=0):
        self.calls.append(("moveTo", x, y))
        if self.raise_on == "moveTo":
            raise RuntimeError("fail-safe triggered")
        if self.moves:
            self._pos = (x, y)

    def click(self, button="left"):
        self.calls.append(("click", button))
        if self.raise_on == "click":
            raise RuntimeError("click blocked")

    def doubleClick(self):
        self.calls.append(("doubleClick",))

    def scroll(self, amount):
        self.calls.append(("scroll", amount))

    def press(self, key):
        self.calls.append(("press", key))

    def mouseUp(self, button="left"):
        pass

    def keyUp(self, key):
        pass
