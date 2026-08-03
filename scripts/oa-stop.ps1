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

Write-Host "OA services stopped."
