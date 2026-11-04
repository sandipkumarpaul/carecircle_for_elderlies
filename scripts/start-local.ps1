param([string]$NodePath = 'node')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $projectRoot 'backend'
$frontend = Join-Path $projectRoot 'frontend'
$logs = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if (!(Test-Path (Join-Path $backend '.env'))) { throw 'Create backend/.env using the README first.' }
$python = Join-Path $backend '.venv/Scripts/python.exe'
if (!(Test-Path $python)) { throw 'Install the Python environment using the README first.' }
$nodeExecutable = (Get-Command $NodePath).Source
if ((& $nodeExecutable --version) -notmatch '^v24\.') { throw 'Use Node 24; pass -NodePath with its full path if needed.' }
function PortOpen([int]$Port) {
    $connection = [System.Net.Sockets.TcpClient]::new()
    try { $connection.Connect('127.0.0.1', $Port); return $true } catch { return $false } finally { $connection.Dispose() }
}
if ((PortOpen 8000) -or (PortOpen 5173)) { throw 'Port 8000 or 5173 is already in use. Stop existing app/test servers first.' }
$localEnv = Get-Content -LiteralPath (Join-Path $backend '.env') -Raw
if ($localEnv -match '127\.0\.0\.1:3307/' -and !(PortOpen 3307)) {
    $runtime = Join-Path (Split-Path $projectRoot -Parent) 'tmp/mysql-runtime'
    $mysql = Get-ChildItem -Path (Join-Path $runtime 'mysql-8.4.*-winx64/bin/mysqld.exe') -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$mysql) { throw 'Start MySQL configured in backend/.env. Optional workspace runtime not found.' }
    $mysqlBase = Split-Path (Split-Path $mysql.FullName -Parent) -Parent
    $dataPath = Join-Path $runtime 'data'
    if (!(Test-Path $dataPath)) { throw 'MySQL data directory is not initialized.' }
    Start-Process -FilePath $mysql.FullName -ArgumentList @('--no-defaults', "--basedir=`"$mysqlBase`"", "--datadir=`"$dataPath`"", '--port=3307', '--bind-address=127.0.0.1', '--mysqlx=OFF', '--console') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'mysql-out.log') -RedirectStandardError (Join-Path $logs 'mysql-error.log') | Out-Null
    for ($attempt = 0; $attempt -lt 20 -and !(PortOpen 3307); $attempt++) { Start-Sleep -Milliseconds 500 }
    if (!(PortOpen 3307)) { throw 'MySQL did not start. See .local/mysql-error.log.' }
}
Push-Location $backend
try { & $python -m alembic upgrade head; if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' } } finally { Pop-Location }
$api = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'api-out.log') -RedirectStandardError (Join-Path $logs 'api-error.log') -PassThru
$vite = Join-Path $frontend 'node_modules/vite/bin/vite.js'
$web = Start-Process -FilePath $nodeExecutable -ArgumentList @("`"$vite`"",'--host','localhost','--port','5173','--strictPort') -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'web-out.log') -RedirectStandardError (Join-Path $logs 'web-error.log') -PassThru
@{ api = $api.Id; web = $web.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs 'processes.json')
Write-Output 'CareCircle starting: http://localhost:5173'
Write-Output 'API docs: http://127.0.0.1:8000/api/docs. Logs: .local/. Stop: scripts/stop-local.ps1.'
