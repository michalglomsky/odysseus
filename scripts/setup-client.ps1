# setup-client.ps1 — Windows laptop: install deps, configure client mode, start Odysseus.
# Run once in PowerShell (as a regular user) after cloning.
# Re-running is safe (idempotent for the .env step).
#
# Prerequisites:
#   - Python 3.10+ in PATH
#   - Git for Windows (for the clone)
#
# Usage:
#   .\scripts\setup-client.ps1 -ServerUrl http://mac-studio.local:7000 -ServerKey <key>
[CmdletBinding()]
param(
    [string]$ServerUrl = "http://mac-studio.local:7000",
    [string]$ServerKey = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

Write-Host "==> Installing Python dependencies..."
pip install -r requirements.txt --quiet

Write-Host "==> Configuring .env (client mode)..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.client.example" ".env"

    (Get-Content ".env") `
        -replace "http://mac-studio\.local:7000", $ServerUrl `
        -replace "replace_with_same_token_as_server", $ServerKey |
        Set-Content ".env"

    Write-Host "  Created .env from .env.client.example."
    if ($ServerKey -eq "") {
        Write-Host ""
        Write-Host "  WARNING: No -ServerKey supplied. Edit .env and set REMOTE_SERVER_KEY before"
        Write-Host "  adding the remote endpoint in the Odysseus Settings UI."
    }
} else {
    Write-Host "  .env already exists — skipping (edit manually if needed)."
}

Write-Host ""
Write-Host "==> Next step: add the Mac Studio endpoint in Odysseus Settings UI:"
Write-Host "      URL:  $ServerUrl/inference/v1/chat/completions"
Write-Host "      Key:  (REMOTE_SERVER_KEY from your .env)"
Write-Host ""
Write-Host "==> Starting Odysseus on localhost:7001..."
Write-Host "    Press Ctrl-C to stop."
Write-Host ""
uvicorn app:app --host 127.0.0.1 --port 7001
