$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Run scripts\run_all_tests.ps1 first." }
& ".\.venv\Scripts\python.exe" -m gesture_control
