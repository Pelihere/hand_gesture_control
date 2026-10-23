@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Gesture Desktop Control - Portable Build

echo ============================================================
echo Gesture Desktop Control - Windows portable build
echo This creates a standalone app folder; Python is not needed
echo on the target PC after the build completes.
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python Launcher 'py' was not found.
  echo Install Python 3.11 x64 from python.org, then run this file again.
  pause
  exit /b 1
)

py -3.11 --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.11 was not found by the Python Launcher.
  echo Install Python 3.11 x64. Other Python versions can remain installed.
  pause
  exit /b 1
)

REM A local file or folder named "mediapipe" would shadow the real package and cause
REM "module 'mediapipe' has no attribute 'solutions'".
if exist "mediapipe" (
  echo ERROR: a file or folder named "mediapipe" exists next to this script and would shadow the library.
  echo Rename or remove it, then run this file again.
  pause
  exit /b 1
)
if exist "mediapipe.py" (
  echo ERROR: mediapipe.py exists next to this script and would shadow the library. Rename it.
  pause
  exit /b 1
)

if not exist ".build-venv\Scripts\python.exe" (
  echo [1/7] Creating isolated Python 3.11 build environment...
  py -3.11 -m venv .build-venv
  if errorlevel 1 goto fail
) else (
  echo [1/7] Re-using build environment .build-venv
)
set "PY=.build-venv\Scripts\python.exe"

"%PY%" -c "import sys; assert sys.version_info[:2]==(3,11), 'build venv is Python %%d.%%d, expected 3.11 - delete the .build-venv folder and rerun' %% sys.version_info[:2]"
if errorlevel 1 goto fail
"%PY%" -c "import struct,sys; assert struct.calcsize('P')*8==64, '64-bit Python is required (MediaPipe has no 32-bit wheels)'"
if errorlevel 1 goto fail

echo [2/7] Installing build tools and application dependencies...
"%PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto fail
"%PY%" -m pip install -e ".[dev,windows,build]"
if errorlevel 1 goto fail
"%PY%" -m pip check
if errorlevel 1 (
  echo ERROR: pip reports conflicting dependency versions in the build environment ^(see above^).
  goto fail
)

echo [3/7] Checking that the MediaPipe Hands API this app needs is really available...
"%PY%" -m gesture_control --check
if errorlevel 1 (
  echo ERROR: dependency check failed ^(see the [FAIL] lines above^).
  goto fail
)

echo [4/7] Running self-test...
"%PY%" scripts\self_test.py
if errorlevel 1 goto fail

echo [5/7] Running automated tests...
"%PY%" -m pytest -q
if errorlevel 1 goto fail

echo [6/7] Building standalone Windows app with PyInstaller...
"%PY%" -m PyInstaller --noconfirm --clean --windowed --onedir --name GestureDesktopControl ^
  --paths src ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  --collect-all PySide6 ^
  --collect-all pyautogui ^
  --collect-all pynput ^
  --collect-all comtypes ^
  --collect-all pycaw ^
  --hidden-import mediapipe.python._framework_bindings ^
  --hidden-import gesture_control.vision.camera_worker ^
  --hidden-import gesture_control.gestures.recognizer ^
  src\gesture_control\__main__.py
if errorlevel 1 goto fail

echo Verifying the PACKAGED app ^(MediaPipe API and model files inside the exe^)...
if exist "%LOCALAPPDATA%\GestureDesktopControl\logs\check.txt" del /q "%LOCALAPPDATA%\GestureDesktopControl\logs\check.txt"
start /wait "" "dist\GestureDesktopControl\GestureDesktopControl.exe" --check
set "CHECK_RC=%ERRORLEVEL%"
if exist "%LOCALAPPDATA%\GestureDesktopControl\logs\check.txt" type "%LOCALAPPDATA%\GestureDesktopControl\logs\check.txt"
if not "%CHECK_RC%"=="0" (
  echo ERROR: the packaged exe failed its own dependency check ^(exit code %CHECK_RC%^).
  goto fail
)

if not exist release mkdir release
if exist release\GestureDesktopControl-Windows-x64.zip del /q release\GestureDesktopControl-Windows-x64.zip

echo [7/7] Creating portable ZIP...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\GestureDesktopControl\*' -DestinationPath 'release\GestureDesktopControl-Windows-x64.zip' -Force"
if errorlevel 1 goto fail

echo.
echo BUILD COMPLETE.
echo App folder: %CD%\dist\GestureDesktopControl
echo Portable ZIP: %CD%\release\GestureDesktopControl-Windows-x64.zip
echo.
echo Copy the ZIP to backup storage now. On the target PC, extract it and run GestureDesktopControl.exe.
echo The build proved the packaged app can load MediaPipe. It did NOT test your webcam or real desktop actions:
echo use the checklist in docs\MANUAL_TEST_PLAN.md ^(Dry-run first, then the Action self-test buttons^).
pause
exit /b 0

:fail
echo.
echo BUILD FAILED. The first error above is the useful one.
echo Keep this window open and copy the error text before retrying.
pause
exit /b 1
