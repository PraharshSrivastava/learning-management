Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Frontend = Resolve-Path (Join-Path $PSScriptRoot "..\employee_frontend")
Set-Location $Frontend

flutter pub get
flutter run -d chrome
