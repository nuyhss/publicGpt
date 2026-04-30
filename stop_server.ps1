$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pidFile = Join-Path $root "server.pid"
$stopped = $false

if (Test-Path $pidFile) {
  $savedPid = Get-Content $pidFile
  if ($savedPid -match '^\d+$') {
    $savedProcess = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
    if ($savedProcess) {
      Stop-Process -Id $savedProcess.Id -Force
      Write-Host "Stopped PublicGPT server PID $savedPid."
      $stopped = $true
    }
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($connections) {
  $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($serverPid in $pids) {
    Stop-Process -Id $serverPid -Force
    Write-Host "Stopped process $serverPid on port 8000."
    $stopped = $true
  }
}

if (-not $stopped) {
  Write-Host "No PublicGPT server is running."
}
