# sync-push.ps1 — commit and push Odysseus data to the sync repo.
# Run at the end of a work session before switching machines.
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

git add -A

$status = git status --porcelain
if (-not $status) {
    Write-Host "Nothing to sync — data is up to date."
    exit 0
}

$msg = "sync $env:COMPUTERNAME $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git commit -m $msg
git push
Write-Host "Pushed: $msg"
