$ErrorActionPreference = "Stop"
Write-Host "=== Gesture Desktop Control: setup and test ==="
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' not found. Install Python 3.11 x64 first." }
py -3.11 --version
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3.11 -m venv .venv }
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[dev,windows]"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $python scripts/self_test.py
if ($LASTEXITCODE -ne 0) { throw "Self-test failed." }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }
Write-Host "=== All automated checks passed. Manual camera/UI checks are still required. ==="
