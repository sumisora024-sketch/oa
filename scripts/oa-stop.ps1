$ErrorActionPreference = "Stop"

$ports = @(8000, 8080)
$currentPid = $PID

foreach ($port in $ports) {
    $listeners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    $processIds = $listeners | Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $processIds) {
        if ($processId -and $processId -ne $currentPid) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped process $processId on port $port"
        }
    }
}

foreach ($pidFile in @("D:\oa\backend\celery-worker.pid", "D:\oa\backend\celery-beat.pid")) {
    if (Test-Path $pidFile) {
        $servicePid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($servicePid) {
            Stop-Process -Id ([int]$servicePid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "OA services stopped."
