$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pidFile = Join-Path $root "server.pid"
$healthUrl = "http://127.0.0.1:8000/health"

try {
  $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
  if ($response.StatusCode -eq 200) {
    $pidText = ""
    if (Test-Path $pidFile) {
      $pidText = Get-Content $pidFile -ErrorAction SilentlyContinue
    }
    if ($pidText -match '^\d+$') {
      Write-Host "PublicGPT server is running. PID=$pidText"
    } else {
      Write-Host "PublicGPT server is running."
    }
    Write-Host "UI: http://127.0.0.1:8000/ui"
    exit 0
  }
} catch {
}

Write-Host "PublicGPT server is not running."
