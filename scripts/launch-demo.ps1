param([string]$DataDir = "", [int]$Port = 8765)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .\.venv\Scripts\python.exe)) { throw "Run the approved setup first" }
$Options = @("demo", "--port", $Port, "--open")
if ($DataDir) { $Options += @("--data-dir", $DataDir) }
.\.venv\Scripts\python.exe run.py @Options
if ($LASTEXITCODE -ne 0) { throw "UtilityOS stopped; inspect the fixed failure code" }
