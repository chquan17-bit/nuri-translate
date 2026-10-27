param(
    [Parameter(Mandatory=$true)][ValidateSet('gemini-3.8-flash','gemini-3.5-flash-lite')][string]$Model,
    [ValidateSet('structured','minimal')][string]$Variant = 'structured'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousEnv = @{}
foreach ($name in @('GEMINI_API_KEY','NURI_API_ENABLED','PYTHONIOENCODING')) {
    $previousEnv[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
    $settingsData = Import-Clixml -LiteralPath (Join-Path $projectRoot '.state\secrets.xml')
    $env:GEMINI_API_KEY = (New-Object System.Net.NetworkCredential('', $settingsData.GeminiKey)).Password
    $env:NURI_API_ENABLED = if ($settingsData.ApiEnabled -eq $true) {'true'} else {'false'}
    $env:PYTHONIOENCODING = 'utf-8'
    & (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'diagnose_provider.py') --model $Model --variant $Variant
} catch {
    Write-Output '{"outcome":"diagnostic_launcher_failed"}'
} finally {
    foreach ($name in $previousEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$previousEnv[$name],'Process') }
    $settingsData = $null
}
