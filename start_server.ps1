$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
$pidFile = Join-Path $root "server.pid"
$outLog = Join-Path $root "server.out.log"
$errLog = Join-Path $root "server.err.log"
$healthUrl = "http://127.0.0.1:8000/health"

function Test-ServerHealth {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

if (-not (Test-Path $python)) {
  Write-Host ".venv Python was not found at $python" -ForegroundColor Red
  Write-Host "Create the virtual environment first, then install dependencies." -ForegroundColor Yellow
  exit 1
}

if (Test-ServerHealth -Url $healthUrl) {
  Write-Host "PublicGPT server is already running." -ForegroundColor Yellow
  Write-Host "UI: http://127.0.0.1:8000/ui" -ForegroundColor Green
  exit 0
}

if (Test-Path $pidFile) {
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$process = Start-Process `
  -FilePath $python `
  -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" `
  -WorkingDirectory $root `
  -WindowStyle Hidden `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -PassThru

Set-Content -Path $pidFile -Value $process.Id

for ($i = 0; $i -lt 10; $i++) {
  Start-Sleep -Seconds 1
  if (Test-ServerHealth -Url $healthUrl) {
    Write-Host "PublicGPT server started in background. PID=$($process.Id)" -ForegroundColor Cyan
    Write-Host "UI: http://127.0.0.1:8000/ui" -ForegroundColor Green
    Write-Host "Health: http://127.0.0.1:8000/health" -ForegroundColor Green
    exit 0
  }
}

Write-Host "Server did not become healthy. Check server.err.log" -ForegroundColor Red
exit 1
