from types import SimpleNamespace
from gesture_control.gestures.recognizer import GestureRecognizer

def landmarks(points):
    return SimpleNamespace(landmark=[SimpleNamespace(x=x,y=y,z=0.0) for x,y in points])

def test_short_landmark_input_is_ignored():
    recognizer = GestureRecognizer()
    assert recognizer.process([SimpleNamespace(x=0,y=0)]*3, now=1.0) == []

def test_point_is_continuous_event():
    pts = [(0.5,0.8)]*21
    # index fingertip/PIP: raised; remaining fingers bent
    pts[8]=(0.5,0.2); pts[6]=(0.5,0.45)
    pts[12]=(0.55,0.6); pts[10]=(0.55,0.45)
    pts[16]=(0.6,0.6); pts[14]=(0.6,0.45)
    pts[20]=(0.65,0.6); pts[18]=(0.65,0.45)
    result=GestureRecognizer().process(landmarks(pts), now=10.0)
    assert any(e.name == "point" and e.continuous for e in result)


def test_static_pose_emits_once_while_held():
    pts = [(0.5,0.8)]*21
    pts[8]=(0.5,0.2); pts[6]=(0.5,0.45)
    pts[12]=(0.55,0.2); pts[10]=(0.55,0.45)
    pts[16]=(0.6,0.6); pts[14]=(0.6,0.45)
    pts[20]=(0.65,0.6); pts[18]=(0.65,0.45)
    recognizer = GestureRecognizer(cooldown=0.1)
    first = recognizer.process(landmarks(pts), now=20.0)
    second = recognizer.process(landmarks(pts), now=21.0)
    assert any(e.name == "peace" for e in first)
    assert not any(e.name == "peace" for e in second)


def test_pinch_uses_relative_palm_scale():
    recognizer = GestureRecognizer(cooldown=0.1)
    pts = [(0.5, 0.5)] * 21
    pts[0] = (0.50, 0.70)
    pts[9] = (0.50, 0.50)
    pts[4] = (0.49, 0.40)
    pts[8] = (0.52, 0.40)
    first = recognizer.process(landmarks(pts), now=30.0)
    assert any(event.name == "pinch" for event in first)

def test_pinch_does_not_trigger_when_fingertips_are_far_apart():
    recognizer = GestureRecognizer(cooldown=0.1)
    pts = [(0.5, 0.5)] * 21
    pts[0] = (0.50, 0.70)
    pts[9] = (0.50, 0.50)
    pts[4] = (0.40, 0.40)
    pts[8] = (0.60, 0.40)
    events = recognizer.process(landmarks(pts), now=40.0)
    assert not any(event.name == "pinch" for event in events)


# ---------------------------------------------------------------- mapping names / swipe vs pointing
def hand(wrist_x, up=(True, True, True, True)):
    """Landmarks for an upright hand; `up` = (index, middle, ring, pinky) extended."""
    pts = [(wrist_x, 0.8)] * 21
    pts[9] = (wrist_x, 0.5)
    pts[4] = (wrist_x - 0.2, 0.5)
    for i, (tip, pip) in enumerate(((8, 6), (12, 10), (16, 14), (20, 18))):
        x = wrist_x + 0.03 * i
        pts[pip] = (x, 0.45)
        pts[tip] = (x, 0.2 if up[i] else 0.6)
    return landmarks(pts)


def sweep(recognizer, up, start_x=0.8, step=-0.07, frames=7):
    events = []
    for i in range(frames):
        events += recognizer.process(hand(start_x + step * i, up), now=100.0 + i * 0.08)
    return [e.name for e in events]


def test_every_recognizer_gesture_has_a_default_mapping():
    from gesture_control.config.settings import DEFAULT_CONFIG
    from gesture_control.gestures.recognizer import GESTURE_NAMES
    assert set(GESTURE_NAMES) == set(DEFAULT_CONFIG["mappings"])


def test_emitted_event_names_are_known_gesture_names():
    from gesture_control.gestures.recognizer import GESTURE_NAMES
    names = set(sweep(GestureRecognizer(cooldown=0.1), (True, True, True, True)))
    names |= set(sweep(GestureRecognizer(cooldown=0.1), (True, False, False, False), start_x=0.2, step=0.07))
    assert names and names <= set(GESTURE_NAMES)


def test_swipe_left_still_detected_with_open_palm():
    assert "swipe_left" in sweep(GestureRecognizer(cooldown=0.1), (True, True, True, True))


def test_swipe_right_still_detected_with_open_palm():
    assert "swipe_right" in sweep(GestureRecognizer(cooldown=0.1), (True, True, True, True), start_x=0.2, step=0.07)


def test_sweeping_the_cursor_while_pointing_does_not_trigger_swipe():
    names = sweep(GestureRecognizer(cooldown=0.1), (True, False, False, False))
    assert "point" in names
    assert not any(n.startswith("swipe") for n in names)
    names = sweep(GestureRecognizer(cooldown=0.1), (True, False, False, False), start_x=0.2, step=0.07)
    assert not any(n.startswith("swipe") for n in names)


def test_current_pose_is_exposed_for_the_ui():
    recognizer = GestureRecognizer()
    recognizer.process(hand(0.5, (True, False, False, False)), now=1.0)
    assert recognizer.current_pose == "point"
    recognizer.reset()
    assert recognizer.current_pose is None
