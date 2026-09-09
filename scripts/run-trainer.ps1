Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Frontend = Resolve-Path (Join-Path $PSScriptRoot "..\frontend")
Set-Location $Frontend

flutter pub get
flutter run -d chrome
