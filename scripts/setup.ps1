param([string]$Wheelhouse = "")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
py -3 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or newer is required'"
if ($LASTEXITCODE -ne 0) { throw "Python version check failed" }
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
}
$InstallOptions = @("--only-binary=:all:", "--disable-pip-version-check")
if ($Wheelhouse) { $InstallOptions += @("--no-index", "--find-links", $Wheelhouse) }
.\.venv\Scripts\python.exe -m pip install @InstallOptions -r requirements-bootstrap.txt
if ($LASTEXITCODE -ne 0) { throw "Installer setup failed" }
.\.venv\Scripts\python.exe -m pip install @InstallOptions -c constraints-tested.txt -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
Write-Output "Setup complete. Run .\.venv\Scripts\python.exe run.py demo --open"
