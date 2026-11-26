$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeArgs = @("compose", "-f", "docker-compose.e2e.yml", "-p", "eamms-release-e2e")
$env:EAMMS_E2E_DB_PASSWORD = [guid]::NewGuid().ToString("N")
$env:EAMMS_E2E_JWT_SECRET = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$env:EAMMS_E2E_API_URL = "http://127.0.0.1:8001"
$env:EAMMS_E2E_WEB_URL = "http://127.0.0.1:3001"
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (Test-Path -LiteralPath $edgePath) {
    $env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = $edgePath
}

$testExit = 1
try {
    Push-Location $repoRoot
    & docker @composeArgs up --build --detach
    if ($LASTEXITCODE -ne 0) { throw "Disposable E2E Compose stack failed to start." }

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $null = Invoke-RestMethod -Uri "$($env:EAMMS_E2E_WEB_URL)/login" -TimeoutSec 3
            $null = Invoke-RestMethod -Uri "$($env:EAMMS_E2E_API_URL)/health/ready" -TimeoutSec 3
            $ready = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ready) { throw "Disposable E2E services did not become ready." }

    Push-Location (Join-Path $repoRoot "frontend")
    try {
        & npm run e2e
        $testExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} catch {
    Write-Error $_
    $testExit = 1
} finally {
    if ((Get-Location).Path -eq (Join-Path $repoRoot "frontend")) { Pop-Location }
    if ((Get-Location).Path -eq $repoRoot) { Pop-Location }
    Push-Location $repoRoot
    & docker @composeArgs down --remove-orphans
    Pop-Location
    Remove-Item Env:EAMMS_E2E_DB_PASSWORD, Env:EAMMS_E2E_JWT_SECRET, Env:EAMMS_E2E_API_URL, Env:EAMMS_E2E_WEB_URL -ErrorAction SilentlyContinue
    Remove-Item Env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH -ErrorAction SilentlyContinue
}

exit $testExit
