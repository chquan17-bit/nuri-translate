param([ValidateSet('run', 'register', 'doctor')][string]$Mode = 'run')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$credentialPath = Join-Path $projectRoot '.state\secrets.xml'
$cloudMarker = Join-Path $projectRoot '.state\cloud-active.json'
if ($Mode -eq 'run' -and (Test-Path -LiteralPath $cloudMarker)) {
    $cloudStatus = Get-Content -LiteralPath $cloudMarker -Raw | ConvertFrom-Json
    if ($cloudStatus.active -eq $true) {
        Write-Host 'Nuri는 Google Cloud Run에서 실행 중입니다. 이 PC에서 별도로 실행할 필요가 없습니다.'
        Write-Host 'Discord에서 /nuri 또는 메시지의 Apps 메뉴를 사용하세요.'
        exit 0
    }
}
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$nuriExitCode = 1
$nuriMutex = $null
$hasMutex = $false
$previousEnv = @{}
foreach ($keyName in @('GEMINI_API_KEY','DISCORD_BOT_TOKEN','GEMINI_MODEL','NURI_API_ENABLED','PYTHONIOENCODING')) {
    $previousEnv[$keyName] = [Environment]::GetEnvironmentVariable($keyName, 'Process')
}
try {
    # Start-Process can inherit a module path containing another PowerShell edition.
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Missing runtime' }
    if (Test-Path -LiteralPath $credentialPath) {
        $nuriCredentials = Import-Clixml -LiteralPath $credentialPath
        $env:GEMINI_API_KEY = (New-Object System.Net.NetworkCredential('', $nuriCredentials.GeminiKey)).Password
        $env:DISCORD_BOT_TOKEN = (New-Object System.Net.NetworkCredential('', $nuriCredentials.DiscordToken)).Password
        $env:GEMINI_MODEL = $nuriCredentials.Model
        $env:NURI_API_ENABLED = if ($nuriCredentials.ApiEnabled -eq $true) { 'true' } else { 'false' }
    }
    if ($Mode -eq 'run') {
        # One running Nuri process for this Windows user/session.
        $nuriMutex = New-Object System.Threading.Mutex($false, 'Local\NuriTranslateGateway')
        try { $hasMutex = $nuriMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $hasMutex = $true }
        if (-not $hasMutex) { throw 'Nuri already running' }
    }
    $env:PYTHONIOENCODING = 'utf-8'
    Push-Location -LiteralPath $projectRoot
    try {
        & $pythonPath -m nuri $Mode
        $nuriExitCode = $LASTEXITCODE
    } finally { Pop-Location }
} catch {
    Write-Host 'Nuri를 시작하지 못했습니다. 연결 설정, 실행 중인 Nuri 창, 설치 폴더를 확인해 주세요.'
} finally {
    foreach ($keyName in $previousEnv.Keys) {
        [Environment]::SetEnvironmentVariable($keyName, $previousEnv[$keyName], 'Process')
    }
    if ($hasMutex) { $nuriMutex.ReleaseMutex() }
    if ($null -ne $nuriMutex) { $nuriMutex.Dispose() }
}
exit $nuriExitCode
