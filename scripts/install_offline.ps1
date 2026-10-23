$ErrorActionPreference = "Stop"
if (-not (Test-Path "wheelhouse")) { throw "wheelhouse folder missing. Run prepare_offline_wheelhouse.ps1 while online, or install dependencies normally." }
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3.11 -m venv .venv }
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --no-index --find-links wheelhouse -e ".[dev,windows]"
if ($LASTEXITCODE -ne 0) { throw "Offline install failed. The wheelhouse may be incomplete or for the wrong Python/architecture." }
& $python scripts/self_test.py
if ($LASTEXITCODE -ne 0) { throw "Self-test failed after offline install." }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Pytest failed after offline install." }
Write-Host "Offline installation and automated tests completed. Manual webcam/UI checks remain necessary."
