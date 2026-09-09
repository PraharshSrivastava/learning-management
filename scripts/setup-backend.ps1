Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Backend = Resolve-Path (Join-Path $PSScriptRoot "..\backend")
Set-Location $Backend

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found on PATH. Install Python 3.12, then rerun this script."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
