# Claude Code handoff prompt: Gesture Desktop Control

## Deployment architecture update (mandatory)
The user needs a low-friction Windows deployment because internet access may be interrupted. The recommended deployment is now a Windows-built PyInstaller **onedir portable app**, created by `BUILD_PORTABLE.bat`. Python 3.11 is used only on the build machine; the resulting app should run on the target Windows PC without a separate Python installation. Do not make the `wheelhouse` workflow the primary path. Preserve the one-click build, run automated tests before packaging, and investigate packaging failures rather than asking the user to manually chase individual dependencies. PyInstaller must be run on Windows to build a Windows executable.


You are taking over an existing Windows/Python project because the user may lose access to international services. **Work offline-first and do not depend on web access.** The existing project is in the current directory. Do not rewrite it from scratch without first inspecting it.

## Mission
Finish, audit, and stabilize a local-first Windows 10/11 webcam hand-gesture desktop controller. The current code is an MVP baseline, not proof of hardware validation. The user has Python 3.15 installed and should use Python 3.11 x64 in a separate virtual environment; project metadata intentionally targets Python >=3.11,<3.13 because MediaPipe support may lag new Python versions. Never uninstall the user's other Python version.

## Mandatory workflow
1. Read README.md, docs/architecture.md, pyproject.toml, all `src/` modules, `tests/`, and `scripts/` before editing.
2. Run `py -3.11 --version`, then `.venv\Scripts\python.exe scripts/self_test.py` and `.venv\Scripts\python.exe -m pytest -q` if dependencies are installed. Record failures accurately.
3. Fix bugs in small coherent changes. Do not claim any test passed unless you ran it and saw its result.
4. Keep the project runnable without network access after dependencies are installed. Do not add cloud APIs, telemetry, remote services, or model downloads.
5. Add/adjust tests for every safety-sensitive change. Run all tests after each logical change and at the end.
6. Update README and docs to match actual behavior. Provide a final report with changed files, exact commands run, test output summary, known limitations, and manual tests the user must do.

## Product requirements
- Windows-first MVP, local-only processing, never save or stream camera frames/video.
- Settings window plus system-tray operation. Camera presence and gesture-control state are separate.
- Global activation shortcut defaults to Ctrl+Alt+G. Emergency stop defaults to Ctrl+Alt+X. Gesture control must always start OFF, including Windows startup/background launch.
- If camera disconnects, immediately disarm, reset gesture state, and release any held mouse/key state. Camera reconnection must NOT automatically re-arm.
- Support tracking up to two hands, but use one hand for primary cursor control initially.
- Absolute and relative cursor modes, adjustable smoothing, static gestures and simple swipes, configurable JSON mappings and UI.
- Dry-run defaults ON and must report recognized actions without performing them. Real actions require the user to explicitly disable dry-run in settings and then explicitly activate control.
- Use an allow-listed action registry. Never execute shell commands, Python expressions, arbitrary paths, or arbitrary code from JSON.
- Allowed initial actions: pointer move, left/right/double click, scroll up/down, volume up/down on Windows, Escape/Enter/Space. Keep extension points clean.
- Start-with-Windows is configurable and only launches the app, never enables gesture control. Avoid writing registry except when the user changes and saves that setting.
- Build custom gesture recording is future work, not part of this MVP. Snap/voice activation and assistant integration are also future work.
- Keyboard/mouse actions must be protected by the central safety gate. The recognizer may emit events only; it must not control the desktop directly.
- Emergency stop must be obvious and reliable. Explain how to recover from hotkey permission/conflict problems.

## Critical audit points
- Inspect whether `pynput` global hotkeys work under target Windows setup; if hotkeys fail, surface an obvious UI warning and keep buttons available.
- Inspect worker thread stop/restart races and camera-state signals. Camera state should not be marked available until initialization succeeds; a normal stop must not leave the controller armed.
- Confirm the main thread never blocks excessively while stopping camera.
- Verify the gesture logic for pinch and swipes, cooldowns/debounce, and gesture transition behavior. Avoid repeated click spam while a pose is held.
- Verify pointer smoothing is actually applied; if not, implement it or remove the misleading setting.
- Confirm relative mode uses deltas and does not jump to an artificial screen center.
- Confirm left-click/right-click mappings don't fire from accidental ambiguous poses; keep dry-run default and consider a deliberate dwell/debounce.
- Confirm camera privacy: no frames are written to disk, included in logs, or captured by screenshots. Logs should only include events/errors.
- Verify config parsing is resilient, schema versioned, and unknown action names are blocked. Preserve invalid config for recovery.
- Verify Windows startup registration uses a safe command and starts disabled. Never require admin privileges if HKCU registration suffices.
- Volume dependencies are optional; gracefully show clear status when absent.
- Test app startup, camera unavailable, camera removal/reconnect, tray close/quit, hotkeys, dry-run, actual action gate, settings persistence, and shutdown release manually where hardware/Windows are available.
- Do not use mock success as proof of real OS input behavior.

## Packaging and offline resilience
- Keep dependencies pinned to compatible ranges. If internet is available, you may prepare a wheelhouse for Python 3.11 x64 using `pip download -d wheelhouse -e .[dev,windows]`, but only if package downloads actually succeed. Include a script for `pip install --no-index --find-links wheelhouse ...` if a wheelhouse is created. Do not promise offline installation without the required wheels.
- Keep all user data/config under `%LOCALAPPDATA%\GestureDesktopControl` on Windows.
- Do not delete the existing stage-1 ZIP or user files.

## Definition of done
- Automated tests pass in the actual Python 3.11 environment, or exact blockers are documented.
- Self-test and test runner work from a clean checkout.
- No action executes while control is OFF, camera is unavailable, emergency stop is latched, or dry-run is ON.
- Camera restoration never re-arms control.
- README has precise setup/run/test instructions and troubleshooting.
- Final answer is Persian, concise but detailed enough to transfer control, and clearly distinguishes automated tests from manual hardware tests.
