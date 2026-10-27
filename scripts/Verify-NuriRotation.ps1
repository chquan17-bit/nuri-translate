# Read-only credential checks. Never print credentials, responses, or exceptions.
param([string]$ApplicationId=$env:NURI_APPLICATION_ID)
$ErrorActionPreference = 'Stop'
if ($ApplicationId -notmatch '^[0-9]{16,22}$') {
    Write-Output 'Set -ApplicationId or NURI_APPLICATION_ID to the intended Discord application ID before checking credentials.'
    exit 2
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot '.state'
$expectedApplicationId = $ApplicationId
$model = $null
$report = [ordered]@{
    verification_completed = $false
    stored_secrets_readable = $false
    google_credential_changed = $false
    discord_credential_changed = $false
    old_google = $null
    old_discord = $null
    new_google_checked = $false
    new_google = $null
    new_discord_checked = $false
    new_discord = $null
    new_discord_application = $null
    new_discord_application_id_matches = $false
    old_credentials_rejected = $false
}
$nuriHttpClient = $null
$nuriHttpHandler = $null
$oldGoogleKey = $null
$oldDiscordToken = $null
$newGoogleKey = $null
$newDiscordToken = $null

function Invoke-NuriCredentialCheck {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Uri,
        [string]$HeaderName,
        [string]$HeaderValue,
        [bool]$CheckApplication = $false
    )
    $result = [ordered]@{
        http_status = $null
        network_error = $false
        access_rejected = $false
        credential_invalid = $false
        success = $false
        application_id_matches = $false
        provider_error_status = $null
        provider_error_reason = $null
    }
    $request = $null
    $response = $null
    try {
        $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Get, $Uri)
        [void]$request.Headers.TryAddWithoutValidation($HeaderName, $HeaderValue)
        $response = $Client.SendAsync($request).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $result.http_status = $status
        $result.success = $status -eq 200
        $result.access_rejected = $status -in @(401, 403)
        # A 403 can mean insufficient permission, so it is not proof of revocation.
        $result.credential_invalid = $status -eq 401
        if (($HeaderName -eq 'x-goog-api-key' -and $status -in @(400, 401, 403)) -or
            ($CheckApplication -and $status -eq 200)) {
            try {
                $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                $payload = $body | ConvertFrom-Json
                if ($CheckApplication) {
                    $result.application_id_matches = [string]$payload.id -ceq $expectedApplicationId
                } else {
                    # Google's invalid-key response can be HTTP 400. Inspect only
                    # its machine-readable reason; never emit the response body.
                    if ($payload.error.status -in @('INVALID_ARGUMENT', 'UNAUTHENTICATED', 'PERMISSION_DENIED')) {
                        $result.provider_error_status = [string]$payload.error.status
                    }
                    foreach ($detail in @($payload.error.details)) {
                        if ($detail.reason -eq 'API_KEY_INVALID') {
                            $result.provider_error_reason = 'API_KEY_INVALID'
                            $result.credential_invalid = $true
                            $result.access_rejected = $true
                        }
                    }
                }
            } catch {
                # Unrecognized responses are inconclusive, not successful checks.
            } finally {
                $body = $null
                $payload = $null
            }
        }
    } catch {
        $result.network_error = $true
    } finally {
        if ($null -ne $response) { $response.Dispose() }
        if ($null -ne $request) { $request.Dispose() }
        $HeaderValue = $null
    }
    return [pscustomobject]$result
}

try {
    Add-Type -AssemblyName System.Net.Http
    $prior = Import-Clixml -LiteralPath (Join-Path $statePath 'rotation-prior.xml')
    $current = Import-Clixml -LiteralPath (Join-Path $statePath 'secrets.xml')
    $model = [string]$current.Model
    if ($model -notmatch '^gemini-[a-z0-9.-]+$') { throw 'Invalid saved model configuration.' }
    foreach ($saved in @($prior, $current)) {
        if ($saved.GeminiKey -isnot [System.Security.SecureString] -or
            $saved.DiscordToken -isnot [System.Security.SecureString]) {
            throw 'Invalid encrypted settings.'
        }
    }
    $oldGoogleKey = (New-Object System.Net.NetworkCredential('', $prior.GeminiKey)).Password
    $oldDiscordToken = (New-Object System.Net.NetworkCredential('', $prior.DiscordToken)).Password
    $newGoogleKey = (New-Object System.Net.NetworkCredential('', $current.GeminiKey)).Password
    $newDiscordToken = (New-Object System.Net.NetworkCredential('', $current.DiscordToken)).Password
    foreach ($value in @($oldGoogleKey, $oldDiscordToken, $newGoogleKey, $newDiscordToken)) {
        if ([string]::IsNullOrWhiteSpace($value)) { throw 'Missing credential.' }
    }
    $report.stored_secrets_readable = $true
    $report.google_credential_changed = $oldGoogleKey -cne $newGoogleKey
    $report.discord_credential_changed = $oldDiscordToken -cne $newDiscordToken
    $nuriHttpHandler = New-Object System.Net.Http.HttpClientHandler
    $nuriHttpHandler.AllowAutoRedirect = $false
    $nuriHttpHandler.UseProxy = $false
    $nuriHttpClient = New-Object System.Net.Http.HttpClient($nuriHttpHandler)
    $nuriHttpClient.Timeout = [TimeSpan]::FromSeconds(20)
    $nuriHttpClient.MaxResponseContentBufferSize = 65536
    $googleUri = 'https://generativelanguage.googleapis.com/v1beta/models/' + $model
    $discordUserUri = 'https://discord.com/api/v10/users/@me'
    $report.old_google = Invoke-NuriCredentialCheck $nuriHttpClient $googleUri 'x-goog-api-key' $oldGoogleKey
    $report.old_discord = Invoke-NuriCredentialCheck $nuriHttpClient $discordUserUri 'Authorization' ('Bot ' + $oldDiscordToken)
    if ($report.google_credential_changed) {
        $report.new_google_checked = $true
        $report.new_google = Invoke-NuriCredentialCheck $nuriHttpClient $googleUri 'x-goog-api-key' $newGoogleKey
    }
    if ($report.discord_credential_changed) {
        $report.new_discord_checked = $true
        $report.new_discord = Invoke-NuriCredentialCheck $nuriHttpClient $discordUserUri 'Authorization' ('Bot ' + $newDiscordToken)
        if ($report.new_discord.success) {
            $report.new_discord_application = Invoke-NuriCredentialCheck $nuriHttpClient 'https://discord.com/api/v10/oauth2/applications/@me' 'Authorization' ('Bot ' + $newDiscordToken) $true
            $report.new_discord_application_id_matches = $report.new_discord_application.application_id_matches
        }
    }
    $report.old_credentials_rejected = $report.old_google.credential_invalid -and $report.old_discord.credential_invalid
    $report.verification_completed = $true
} catch {
    # Deliberately suppress all exception objects and secret-bearing diagnostics.
} finally {
    if ($null -ne $nuriHttpClient) { $nuriHttpClient.Dispose() }
    if ($null -ne $nuriHttpHandler) { $nuriHttpHandler.Dispose() }
    $oldGoogleKey = $null
    $oldDiscordToken = $null
    $newGoogleKey = $null
    $newDiscordToken = $null
    $prior = $null
    $current = $null
    $saved = $null
    $value = $null
}
$report | ConvertTo-Json -Depth 5 -Compress
if (-not $report.verification_completed) { exit 1 }
