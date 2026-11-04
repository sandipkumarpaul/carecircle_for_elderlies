$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$record = Join-Path $projectRoot '.local/processes.json'
if (!(Test-Path $record)) { Write-Output 'No recorded app processes.'; exit }
$ids = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach ($processId in @($ids.api, $ids.web)) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if (!$process) { continue }
    if (($process.ExecutablePath -and $process.ExecutablePath.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) -or ($process.CommandLine -and $process.CommandLine.Contains($projectRoot))) {
        foreach ($child in (Get-CimInstance Win32_Process -Filter "ParentProcessId = $processId")) {
            if ($child.CommandLine -match 'uvicorn app.main:app') { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
        }
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
}
Write-Output 'Stopped recorded app servers. MySQL remains running for development.'
