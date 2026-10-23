# Manual test plan (Windows 10/11)

Run automated checks first. Keep **Dry-run ON** for tests 1–7.

## A. Automated checks
- [ ] `python scripts/self_test.py` completes with PASS.
- [ ] `python -m pytest -q` passes.
- [ ] `python -m compileall -q src tests scripts` exits without errors.

## A2. Packaged-app check
- [ ] `GestureDesktopControl.exe --check` (the build runs this) writes `%LOCALAPPDATA%\GestureDesktopControl\logs\check.txt` ending in `RESULT: PASS`.

## B. Camera and UI
- [ ] Launch with the laptop camera privacy switch open and confirm preview appears.
- [ ] Show one hand, then two hands. Landmarks should be drawn for both; only the first detected hand controls the primary cursor mapping.
- [ ] Stop the camera from the UI. Confirm preview stops and status says control is disarmed.
- [ ] Start the camera again. Confirm control remains OFF until explicitly activated.
- [ ] With the app running, block camera access using the physical privacy switch or disconnect an external camera. Confirm control disarms. Restore camera and confirm it does not auto-arm.
- [ ] Close the window. It should hide to tray and disarm control. Reopen it from the tray.
- [ ] Use tray > Quit and confirm the app exits cleanly.

## C. Gesture recognition and safety (dry-run)
- [ ] Try point, pinch, peace, open palm, fist, thumbs-up, and short left/right swipes in good lighting.
- [ ] Confirm recognized events appear in the event log. Static gestures should not repeatedly trigger while held.
- [ ] Press Ctrl+Alt+G. Status should show ON (DRY RUN).
- [ ] Confirm no mouse click, cursor movement, key press, or volume change occurs while dry-run is enabled.
- [ ] Press Ctrl+Alt+X. Confirm emergency stop latches and activation hotkey cannot re-arm until reset.
- [ ] Reset emergency stop in UI, then explicitly activate again.

## D. Settings and configuration
- [ ] Change camera index, cursor mode, smoothing, max hands, dry-run and a gesture mapping; save and restart. Confirm settings persist.
- [ ] Inspect `%LOCALAPPDATA%\GestureDesktopControl\settings.json`. It should contain action identifiers only, not executable code.
- [ ] Test a deliberately invalid action name in JSON. It must be blocked, never executed.
- [ ] If testing startup registration, toggle it in settings and save. Verify startup launches the app with control OFF; turn the option off and save after the test.

## D2. Action self-test (independent of webcam and gestures)
- [ ] With Dry-run ON, click **Test cursor**: dialog says "Dry run - nothing happened"; the cursor does not move.
- [ ] Uncheck Dry-run (control turns OFF). Click **Test cursor**: the cursor jumps 40 px and back; dialog says a real action was performed. No click, no typing.
- [ ] Click **Test volume** at a low volume: it rises 2 % and is restored; dialog reports the levels. If it says FAILED, read the error (audio endpoint / `pycaw`).

## E. Real actions (only after dry-run is proven)
- [ ] Uncheck Dry-run (applies immediately and turns control OFF; Save to keep it). The status bar must say `Mode: LIVE`. Press Activate: it must say `Control ON (LIVE)`.
- [ ] Each gesture must produce one event-log line ending in `EXECUTED` (or an explicit BLOCKED / FAILED / NOT MAPPED reason).
- [ ] Test cursor movement on a harmless empty desktop area first.
- [ ] Test click mappings on a harmless target, not a destructive button or unsaved document.
- [ ] Test Escape/Enter/Space only in a disposable text editor.
- [ ] Test volume controls at a low volume.
- [ ] Test Ctrl+Alt+X and camera loss while control is ON. Confirm input is released and no further actions occur.
- [ ] Re-enable dry-run after testing.

## Report format
For any failure, record: Python version, exact command, full traceback or status text, whether dry-run was ON, and whether the camera preview was working. Do not include camera images or video.
