# Gesture Desktop Control

Local-first Windows 10/11 hand-gesture desktop controller. Camera frames are processed in memory and are not saved or uploaded.

## New recommended workflow: build a portable Windows app once

The old `wheelhouse` workflow is no longer the recommended route. It required manually maintaining a complete set of compatible wheels and build dependencies, which is a spectacularly unnecessary hobby.

1. Install **Python 3.11 x64** once on the development laptop. Python 3.15 can remain installed alongside it.
2. While internet is available, extract this project and double-click **`BUILD_PORTABLE.bat`**.
3. The script explicitly uses `py -3.11`, creates an isolated `.build-venv`, installs dependencies, checks for dependency conflicts and for the MediaPipe `solutions` API, runs the self-test and pytest, builds a PyInstaller one-folder app, and then runs the **packaged exe** with `--check` to prove MediaPipe and its model files were really bundled. Any failure stops the build.
4. When it finishes, copy `release/GestureDesktopControl-Windows-x64.zip` to a USB drive or external disk.
5. On the target Windows PC, extract the ZIP and run `GestureDesktopControl.exe`. Python does not need to be installed on that target PC.

The first build requires internet to download Python packages. Run the build before connectivity is lost. Do not delete `.build-venv` until the build and backup are complete. The package is built on Windows because PyInstaller does not produce Windows executables when run on Linux/macOS.

If the build fails, keep the terminal open and copy the **first error**, not only the final summary. The script stops at the first failed step.

## Why "recognized but nothing happens" - read the status bar and the event log
The window now shows one always-visible line, e.g. `Camera OK | Control ON (LIVE) | Mode: LIVE | Seeing: point`, and the event log lists **every detected gesture and what happened to it**:

| Log line | Meaning |
|---|---|
| (no line, `Seeing: no hand`) | 1. gesture not detected: lighting/framing/camera problem |
| `fist -> none: NOT MAPPED - ...` | 2. detected but no usable mapping (missing, disabled, or action `none`) |
| `pinch -> left_click: BLOCKED - control is OFF - press Activate (Ctrl+Alt+G)` | 3. mapped, but a safety condition (control OFF, camera lost, emergency stop) or a gesture/action mismatch stopped it |
| `pinch -> left_click: FAILED - <error>` | 4. the action was attempted and the backend (pyautogui / Windows audio) raised an error |
| `pinch -> left_click: DRY RUN (nothing sent)` | 5a. simulated only: Dry-run is ON |
| `pinch -> left_click: EXECUTED` | 5b. the real action was sent to Windows |

Things that used to fail silently and no longer do:
- Control starts OFF every launch: press **Activate** (button, tray, or `Ctrl+Alt+G`) before gestures do anything.
- Dry-run starts ON. Unchecking it now takes effect immediately (and turns control OFF so you must press Activate again on purpose); **Save settings** only makes it permanent. The status bar shows `unsaved changes` until you save.
- Mapping / cursor-mode / smoothing edits used to apply only after "Save settings"; they now apply immediately.
- `Ctrl+Alt+G` / `Ctrl+Alt+X` are matched by virtual-key code, so they also work while a non-Latin keyboard layout (e.g. Persian) is active. If global hotkeys cannot start, a red banner says so and the buttons still work.
- Pointing and sweeping your hand to steer the cursor no longer also fires `swipe_left/right` (which changed the volume).

### Action self-test (no webcam, no gestures)
Uncheck Dry-run, then use **Test cursor** (moves the pointer 40 px and back) or **Test volume** (+2 % then restores it). Neither clicks or types. The result is one of: *real action performed*, *Dry run - nothing happened*, or *FAILED* with the error. If the self-test passes but gestures still do nothing, read the event log lines above; if it fails, the problem is the Windows backend, not the camera.

## Safety defaults
- Gesture control starts OFF every time.
- Dry-run starts ON. In dry-run the app reports actions but does not move/click/type/change volume.
- `Ctrl+Alt+G`: activate/deactivate gesture control.
- `Ctrl+Alt+X`: emergency stop. It latches until reset in the UI or app restart.
- Camera loss immediately disarms control. Reconnecting the camera never automatically reactivates it.
- JSON mappings can select only predefined action names; no shell commands or arbitrary code are supported.

## Gestures and actions
- `point`: index finger extended; continuous cursor movement.
- `pinch`: thumb/index pinch transition; default mapped to left click.
- `peace`: index and middle fingers raised; default mapped to right click.
- `swipe_left` / `swipe_right`: short wrist movement; default mapped to volume down/up.
- `open_palm`, `fist`, `thumbs_up`: recognized, default action `none`.

Mappings are editable in the UI and saved to `%LOCALAPPDATA%\GestureDesktopControl\settings.json`. Available actions include `none`, `pointer_move`, `left_click`, `right_click`, `double_click`, `scroll_up`, `scroll_down`, `volume_up`, `volume_down`, `escape`, `enter`, and `space`.

## Privacy and logs
Settings and logs are stored under `%LOCALAPPDATA%\GestureDesktopControl`. The app logs status and recognized/action events, not camera frames. There is no video recording or network streaming code.

## Dependency note (MediaPipe)
The app uses the legacy `mp.solutions.hands` API. `mediapipe==0.10.21` on Python 3.11 provides it; newer releases (e.g. 0.10.32) no longer expose it and fail with `module 'mediapipe' has no attribute 'solutions'`. `numpy` is limited to `<2` because MediaPipe 0.10.21 requires it. A local file/folder called `mediapipe` also causes the same error by shadowing the package; the build refuses to run if it finds one. To check any install at any time: `python -m gesture_control --check` (from source) or `GestureDesktopControl.exe --check` (packaged); the report goes to `%LOCALAPPDATA%\GestureDesktopControl\logs\check.txt`.

## Testing
`BUILD_PORTABLE.bat` runs `scripts/self_test.py` and `pytest` before packaging. These automated tests do not validate physical webcam behavior or real Windows input/audio behavior. After building, manually test:

1. App opens and webcam preview works.
2. One and two hands are detected in good lighting.
3. Dry-run logs gestures without moving the cursor or clicking.
4. Emergency stop disarms actions immediately.
5. Disconnecting the camera disarms control; reconnecting does not re-enable it.
6. Only after these pass, disable dry-run and test actual actions carefully.

## Project files
- `BUILD_PORTABLE.bat`: one-click Windows build and automated test runner.
- `scripts/self_test.py`: smoke test.
- `tests/`: automated tests.
- `docs/architecture.md`: architecture and safety boundaries.
- `docs/MANUAL_TEST_PLAN.md`: manual hardware test checklist.
- `docs/CLAUDE_CODE_HANDOFF_PROMPT.md`: handoff instructions for Claude Code.

## Troubleshooting
- `py -3.11` not found: install Python 3.11 x64; do not uninstall Python 3.15.
- Missing camera: check the physical camera privacy switch and Windows Settings > Privacy & security > Camera; try another camera index.
- Preview but no landmarks: improve lighting, keep the hand in frame, and face the palm toward the camera.
- Gestures recognized but nothing happens: see "Why recognized but nothing happens" above, then run the self-test buttons.
- Global hotkeys do not work: check conflicts and inspect `%LOCALAPPDATA%\GestureDesktopControl\logs\application.log`.
- Volume controls unavailable: check the default audio endpoint and `pycaw` dependency installation.

## Claude Code handoff
Read `docs/CLAUDE_CODE_HANDOFF_PROMPT.md` and paste it into Claude Code with this project folder open. Preserve the portable-build architecture unless a concrete tested issue requires changing it.
