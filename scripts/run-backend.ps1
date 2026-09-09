Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Backend = Resolve-Path (Join-Path $PSScriptRoot "..\backend")
Set-Location $Backend

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Backend virtual environment is missing. Run .\scripts\setup-backend.ps1 first."
}

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
