$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
$pidFile = Join-Path $root "server.pid"
$outLog = Join-Path $root "server.out.log"
$errLog = Join-Path $root "server.err.log"

if (-not (Test-Path $python)) {
  Write-Host ".venv Python was not found at $python" -ForegroundColor Red
  Write-Host "Create the virtual environment first, then install dependencies." -ForegroundColor Yellow
  exit 1
}

if (Test-Path $pidFile) {
  $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
  if ($existingPid -match '^\d+$') {
    $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
    if ($existingProcess) {
      Write-Host "PublicGPT server is already running. PID=$existingPid" -ForegroundColor Yellow
      Write-Host "UI: http://127.0.0.1:8000/ui" -ForegroundColor Green
      exit 0
    }
  }
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
Start-Sleep -Seconds 3

if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
  Write-Host "PublicGPT server started in background. PID=$($process.Id)" -ForegroundColor Cyan
  Write-Host "UI: http://127.0.0.1:8000/ui" -ForegroundColor Green
  Write-Host "Health: http://127.0.0.1:8000/health" -ForegroundColor Green
  exit 0
}

Write-Host "Server process exited during startup. Check server.err.log" -ForegroundColor Red
exit 1
