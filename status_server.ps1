$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pidFile = Join-Path $root "server.pid"
$running = $false

if (Test-Path $pidFile) {
  $savedPid = Get-Content $pidFile
  if ($savedPid -match '^\d+$') {
    $savedProcess = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
    if ($savedProcess) {
      Write-Host "PublicGPT server is running. PID=$savedPid"
      Write-Host "UI: http://127.0.0.1:8000/ui"
      $running = $true
    }
  }
}

if (-not $running) {
  Write-Host "PublicGPT server is not running."
}
