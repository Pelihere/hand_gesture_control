BUILD SUMMARY

Preferred path: double-click BUILD_PORTABLE.bat on Windows while online.
Output: release/GestureDesktopControl-Windows-x64.zip
Build Python: Python 3.11 x64 (Python 3.15 can stay installed).
Target PC: does not need Python installed.

Automated tests are run before packaging. Physical webcam, hotkeys, audio and actual desktop actions still require manual Windows testing. Start with Dry-run enabled.

The build stops on: wrong Python version/bitness, a local 'mediapipe' file or folder shadowing the library, conflicting dependency versions (pip check), a missing mediapipe.solutions API, failing tests, or the packaged exe failing its own `--check`.
Output of the packaged check: %LOCALAPPDATA%\GestureDesktopControl\logs\check.txt
