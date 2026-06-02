# sync-pull.ps1 — pull latest Odysseus data before starting a work session.
# Run at the start of a session after switching machines.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DataDir = Join-Path (Split-Path -Parent $PSScriptRoot) "data"

if (-not (Test-Path (Join-Path $DataDir ".git"))) {
    Write-Error "ERROR: $DataDir is not a git repo. Run scripts/setup-data-sync.ps1 first."
    exit 1
}

Set-Location $DataDir

Write-Host "Pulling latest data..."
git pull --rebase
Write-Host "Done — data is up to date."
