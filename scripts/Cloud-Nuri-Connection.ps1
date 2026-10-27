param(
    [ValidateSet('inspect','upload','switch','restore')][string]$Mode='inspect',
    [string]$Endpoint='',
    [string]$ApplicationId=$env:NURI_APPLICATION_ID,
    [string]$Project=$env:NURI_CLOUD_PROJECT,
    [string]$Account=$env:NURI_GCLOUD_ACCOUNT
)
$ErrorActionPreference='Stop'
if ($ApplicationId -notmatch '^[0-9]{16,22}$' -or $Project -notmatch '^[a-z][a-z0-9-]{4,61}[a-z0-9]$') {
    Write-Output 'Set -ApplicationId and -Project, or NURI_APPLICATION_ID and NURI_CLOUD_PROJECT, before using this maintenance script.'
    exit 2
}
if ($Mode -eq 'upload' -and $Account -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') {
    Write-Output 'Set -Account or NURI_GCLOUD_ACCOUNT to the intended Google account before upload.'
    exit 2
}
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
$nuriRoot=Split-Path -Parent $PSScriptRoot
$nuriOldEnv=@{}
foreach($nuriName in @('DISCORD_BOT_TOKEN','GEMINI_API_KEY','GEMINI_MODEL')) { $nuriOldEnv[$nuriName]=[Environment]::GetEnvironmentVariable($nuriName,'Process') }
try {
    $nuriSaved=Import-Clixml -LiteralPath (Join-Path $nuriRoot '.state\secrets.xml')
    $env:DISCORD_BOT_TOKEN=(New-Object System.Net.NetworkCredential('', $nuriSaved.DiscordToken)).Password
    $env:GEMINI_API_KEY=(New-Object System.Net.NetworkCredential('', $nuriSaved.GeminiKey)).Password
    $env:GEMINI_MODEL=$nuriSaved.Model
    $nuriArgs=@((Join-Path $PSScriptRoot 'cloud_connection.py'),$Mode,'--application-id',$ApplicationId,'--project',$Project)
    if ($Account) { $nuriArgs+=@('--account',$Account) }
    if ($Endpoint) { $nuriArgs+=@('--endpoint',$Endpoint) }
    & (Join-Path $nuriRoot '.venv\Scripts\python.exe') @nuriArgs
    $nuriResult=$LASTEXITCODE
} catch { Write-Output '{"success":false,"stage":"load-existing-connection"}'; $nuriResult=1 }
finally { foreach($nuriName in $nuriOldEnv.Keys) { [Environment]::SetEnvironmentVariable($nuriName,$nuriOldEnv[$nuriName],'Process') }; $nuriSaved=$null }
exit $nuriResult
