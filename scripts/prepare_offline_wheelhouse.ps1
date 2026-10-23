$ErrorActionPreference = "Stop"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' not found." }
py -3.11 --version
New-Item -ItemType Directory -Force -Path "wheelhouse" | Out-Null
# Run this NOW while internet is available, on Windows x64 with Python 3.11.
# --only-binary avoids downloads that would need a compiler during offline installation.
py -3.11 -m pip download --only-binary=:all: --dest wheelhouse `
  "numpy>=1.26,<2.2" `
  "opencv-python>=4.10,<4.12" `
  "mediapipe>=0.10.20,<0.11" `
  "PySide6>=6.8,<6.10" `
  "pyautogui>=0.9.54,<0.10" `
  "pynput>=1.7.7,<1.9" `
  "pycaw>=20240210" `
  "comtypes>=1.4.8" `
  "pytest>=8.0,<9" `
  "pytest-cov>=5.0,<7" `
  "setuptools>=69" `
  "wheel" `
  "pyinstaller>=6.10,<7"
if ($LASTEXITCODE -ne 0) { throw "Wheel download failed. Resolve the package/version error while internet is available, then rerun." }
Write-Host "Wheelhouse created. Keep the wheelhouse folder together with the project ZIP or copy it to external storage."
Get-ChildItem wheelhouse | Measure-Object -Property Length -Sum | ForEach-Object { Write-Host ("Files: {0}; total MB: {1:N1}" -f $_.Count, ($_.Sum / 1MB)) }
