param([string]$Wheelhouse = "")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$InstallOptions = @()
if ($Wheelhouse) { $InstallOptions += @("--directory", $Wheelhouse) }
py -3.13 scripts/dependency_artifacts.py install @InstallOptions
if ($LASTEXITCODE -ne 0) { throw "Reviewed dependency installation failed; inspect the fixed failure code" }
Write-Output "Setup complete. Run .\.venv\Scripts\python.exe run.py demo --open"
Write-Output "Staff setup: .\.venv\Scripts\python.exe run.py staff --choose-data-dir --open"
