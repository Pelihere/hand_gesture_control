# Architecture and safety invariants

- `vision/`: webcam capture and MediaPipe landmarks; frames remain in RAM.
- `gestures/`: converts landmarks to gesture events only; no OS actions here.
- `core/safety.py`: single gate for camera availability, explicit arm/disarm, and emergency stop.
- `core/controller.py`: maps events to configured allow-listed action names and gates all execution. Every event ends in exactly one reported outcome: not mapped, blocked (with reason), failed, dry-run or executed.
- `actions/executor.py`: allow-listed OS actions, dry-run default, best-effort input release. Returns an `ActionResult` (executed / dry_run / failed / blocked / noop) and provides the webcam-independent self-test.
- `config/`: validated, versioned JSON settings stored in the user's local application data directory.
- `input/`: global activation/emergency hotkeys, matched by virtual-key code so they work under any keyboard layout.
- `ui/`: preview, mapping table, status, tray and settings.
- `platform/`: Windows-only integrations such as startup registration and Core Audio volume.

## Invariants
1. Control starts disabled on every launch.
2. Camera loss disarms control and releases any held input state.
3. Camera restoration does not arm control.
4. Dry-run is enabled by default and logs intended actions only.
5. JSON contains action identifiers, never executable code or shell commands.
6. Every actual action passes through the central safety gate and allow-list.
7. No video/image is written to disk. Logs contain operational status only.
8. Gesture recognition cannot directly call mouse/keyboard APIs.
9. A blocked, failed or simulated action is never reported as executed.
10. Switching Dry-run on/off turns control OFF; the user must activate again explicitly.

## Current known MVP limitations
- Gesture geometry is heuristic and can vary with camera angle, hand orientation and lighting.
- Relative cursor movement and smoothing require validation on actual hardware.
- Windows global hotkeys can be affected by OS policy or other applications.
- Real camera/hotkey/volume behavior cannot be certified by unit tests alone.
