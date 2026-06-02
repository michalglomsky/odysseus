# setup-data-sync.ps1 — one-time setup on Windows: init the data/ git repo
# and link it to the private GitHub sync repo.
#
# Usage:
#   .\scripts\setup-data-sync.ps1 -Remote https://github.com/<you>/odysseus-data.git
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Remote
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DataDir = Join-Path (Split-Path -Parent $PSScriptRoot) "data"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
Set-Location $DataDir

if (-not (Test-Path ".git")) {
    git init -b main
    Write-Host "Initialized git repo in $DataDir"
}

$existingRemote = git remote get-url origin 2>$null
if (-not $existingRemote) {
    git remote add origin $Remote
    Write-Host "Remote set to $Remote"
} else {
    Write-Host "Remote already set: $existingRemote"
}

# Check if remote has commits (second machine setup).
$hasRemote = git ls-remote --exit-code origin main 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Remote has data — pulling..."
    git fetch origin main
    git reset --hard origin/main
} else {
    git add -A
    $staged = git diff --cached --quiet; $hasSomething = $LASTEXITCODE -ne 0
    if ($hasSomething) {
        git commit -m "initial data snapshot $(Get-Date -Format 'yyyy-MM-dd')"
    } else {
        git commit --allow-empty -m "initial commit"
    }
    git push -u origin main
    Write-Host "Initial snapshot pushed."
}

Write-Host ""
Write-Host "Setup complete. Workflow:"
Write-Host "  End of session:   .\scripts\sync-push.ps1"
Write-Host "  Start of session: .\scripts\sync-pull.ps1"
