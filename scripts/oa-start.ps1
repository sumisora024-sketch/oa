$ErrorActionPreference = "Stop"

$root = "D:\oa"
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendLog = Join-Path $backendDir "backend.log"
$backendErrLog = Join-Path $backendDir "backend.err.log"
$frontendLog = Join-Path $frontendDir "frontend.log"
$frontendErrLog = Join-Path $frontendDir "frontend.err.log"

if (!(Test-Path $backendPython)) {
    throw "Backend virtualenv python was not found: $backendPython"
}

function Test-DockerReady {
    try {
        docker info *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Wait-DockerReady {
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-DockerReady) {
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "Docker daemon is not ready. Please start Docker Desktop and rerun this script."
}

if (!(Test-DockerReady)) {
    $dockerService = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    if ($dockerService -and $dockerService.Status -ne "Running") {
        try {
            Start-Service -Name "com.docker.service"
        }
        catch {
            Write-Warning "Could not start com.docker.service directly. Trying Docker Desktop instead."
        }
    }

    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktop) {
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    }

    Wait-DockerReady
}

Push-Location $root
try {
    docker compose up -d mysql redis
}
finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot "oa-stop.ps1")
Start-Sleep -Seconds 1

Start-Process `
    -FilePath $backendPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog

Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory $frontendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErrLog

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$Retries = 30
    )

    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $response.StatusCode
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    throw "Timed out waiting for $Url"
}

$backendStatus = Wait-HttpOk "http://127.0.0.1:8000/api/health"
$frontendStatus = Wait-HttpOk "http://127.0.0.1:8080"

Write-Host "Backend:  $backendStatus http://127.0.0.1:8000"
Write-Host "Frontend: $frontendStatus http://127.0.0.1:8080"
Write-Host "Logs:"
Write-Host "  $backendLog"
Write-Host "  $backendErrLog"
Write-Host "  $frontendLog"
Write-Host "  $frontendErrLog"
