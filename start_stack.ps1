<#!
  DX-LAB local stack — opens separate PowerShell windows for each long-running service.
  Run from repo root:  .\start_stack.ps1

  Prereqs: Python envs/deps installed per docs/integration.md (uvicorn, hub requirements, etc.).
#>
$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$Backend = Join-Path $RepoRoot "backend"

function Start-ServiceWindow {
    param([string]$Title, [string]$WorkingDirectory, [string]$Command)
    $wd = (Resolve-Path $WorkingDirectory).Path
    $args = "-NoExit", "-Command", "Set-Location -LiteralPath '$wd'; Write-Host '=== $Title ===' -ForegroundColor Cyan; $Command"
    $shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
    Start-Process -FilePath $shell -ArgumentList $args -WindowStyle Normal
}

Write-Host "Launching stack in new windows (ITD :8000, Drug safety :8002, 3D :5000, ACP :8010)..." -ForegroundColor Green
Write-Host "Close each window to stop that service." -ForegroundColor Yellow

Start-ServiceWindow "ITD / Data Manager" (Join-Path $Backend "services\data_manager") "uvicorn api_server:app --host 127.0.0.1 --port 8000"
Start-Sleep -Milliseconds 400
Start-ServiceWindow "Drug safety" (Join-Path $Backend "services\drug_safety") "python run_web.py"
Start-Sleep -Milliseconds 400
Start-ServiceWindow "3D printer (Flask)" (Join-Path $Backend "services\printer_3d") "python web_server.py"
Start-Sleep -Milliseconds 400
Start-ServiceWindow "ACP hub" $Backend "python -m acp_hub.main"

Write-Host ""
Write-Host "Optional: Next.js — in another terminal:  cd frontend && npm run dev" -ForegroundColor Cyan
Write-Host "Frontend can call ACP via same-origin proxy:  /api/acp/agents  (see frontend/.env.example)" -ForegroundColor Cyan
