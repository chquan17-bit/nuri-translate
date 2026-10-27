# Run this script yourself. Tokens are never sent to Codex or written in plaintext.
$ErrorActionPreference = 'Stop'
# A child Windows PowerShell can inherit a module path from Codex's newer runtime.
# Load this process's built-in modules explicitly before accepting any input.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
$null = Get-Command Microsoft.PowerShell.Security\ConvertTo-SecureString -ErrorAction Stop
$null = Get-Command Microsoft.PowerShell.Utility\Export-Clixml -ErrorAction Stop
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot '.state'

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Nuri 연결 설정 · 저장 확인'
$form.ClientSize = New-Object System.Drawing.Size(560, 430)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Malgun Gothic', 10)
$form.BackColor = [System.Drawing.ColorTranslator]::FromHtml('#F5F0E5')

$intro = New-Object System.Windows.Forms.Label
$intro.Text = "Nuri 번역 · QUAN CHENGHAO · 권성호`r`nGemini 3.5 Flash-Lite / Discord 개인 앱"
$intro.SetBounds(24, 20, 515, 55)
$form.Controls.Add($intro)
$googleLabel = New-Object System.Windows.Forms.Label
$googleLabel.Text = 'Google AI Studio의 무료 티어 프로젝트 API 키'
$googleLabel.SetBounds(24, 85, 510, 25)
$form.Controls.Add($googleLabel)
$googleBox = New-Object System.Windows.Forms.TextBox
$googleBox.SetBounds(24, 115, 510, 30)
$googleBox.UseSystemPasswordChar = $true
$form.Controls.Add($googleBox)
$discordLabel = New-Object System.Windows.Forms.Label
$discordLabel.Text = '새 Nuri Discord 앱의 Bot Token'
$discordLabel.SetBounds(24, 158, 510, 25)
$form.Controls.Add($discordLabel)
$discordBox = New-Object System.Windows.Forms.TextBox
$discordBox.SetBounds(24, 188, 510, 30)
$discordBox.UseSystemPasswordChar = $true
$form.Controls.Add($discordBox)
$confirmed = New-Object System.Windows.Forms.CheckBox
$confirmed.Text = 'Google 프로젝트가 Free Tier임을 확인했습니다.'
$confirmed.SetBounds(24, 232, 510, 28)
$form.Controls.Add($confirmed)
$note = New-Object System.Windows.Forms.Label
$note.Text = "새 키는 위의 입력 칸에 붙여 넣으세요.`r`n.cmd 실행 파일이나 채팅에는 키를 입력하지 마세요.`r`n이 Windows 사용자만 복호화할 수 있게 저장됩니다."
$note.SetBounds(24, 270, 515, 75)
$form.Controls.Add($note)
$save = New-Object System.Windows.Forms.Button
$save.Text = '암호화해 저장'
$save.SetBounds(350, 375, 185, 34)
$form.Controls.Add($save)
$save.Add_Click({
    if (-not $confirmed.Checked -or [string]::IsNullOrWhiteSpace($googleBox.Text) -or [string]::IsNullOrWhiteSpace($discordBox.Text)) {
        [void][System.Windows.Forms.MessageBox]::Show('두 연결 값과 Free Tier 확인이 필요합니다.', 'Nuri')
        return
    }
    $saveStage = 'create-directory'
    try {
        [void][System.IO.Directory]::CreateDirectory($statePath)
        $saveStage = 'encrypt-inputs'
        $settingsData = @{
            GeminiKey = Microsoft.PowerShell.Security\ConvertTo-SecureString -String $googleBox.Text.Trim() -AsPlainText -Force
            DiscordToken = Microsoft.PowerShell.Security\ConvertTo-SecureString -String $discordBox.Text.Trim() -AsPlainText -Force
            ApiEnabled = $true
            Model = 'gemini-3.5-flash-lite'
        }
        $saveStage = 'write-encrypted-file'
        $settingsData | Microsoft.PowerShell.Utility\Export-Clixml -LiteralPath (Join-Path $statePath 'secrets.xml') -Force
        $saveStage = 'clear-inputs'
        $googleBox.Clear()
        $discordBox.Clear()
        $saveStage = 'show-success'
        [void][System.Windows.Forms.MessageBox]::Show('새 연결 값을 암호화해 저장했습니다. Codex에 저장 완료라고 알려주세요.', 'Nuri')
        $form.Close()
    } catch {
        # Never log Message, InvocationInfo, ScriptStackTrace, inputs, or settingsData.
        $saveFailure = [ordered]@{
            observed_at = [DateTimeOffset]::Now.ToString('o')
            stage = $saveStage
            exception_type = $_.Exception.GetType().Name
            hresult = $_.Exception.HResult
            inner_exception_type = $null
            inner_hresult = $null
            state_path_matches = $statePath -ceq (Join-Path $projectRoot '.state')
        }
        if ($null -ne $_.Exception.InnerException) {
            $saveFailure.inner_exception_type = $_.Exception.InnerException.GetType().Name
            $saveFailure.inner_hresult = $_.Exception.InnerException.HResult
        }
        try {
            $saveFailure | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $statePath 'config-save-diagnostic.json') -Encoding UTF8
        } catch {
            # The fixed-code dialog still works when the diagnostic path is unwritable.
        }
        [void][System.Windows.Forms.MessageBox]::Show("저장에 실패했습니다. 입력한 값은 이 창에 그대로 있습니다.`r`n키 값 없이 오류 코드만 기록했습니다.`r`n단계: $saveStage / 코드: $($saveFailure.hresult)`r`n이 창을 그대로 두고 Codex에 알려주세요.", 'Nuri 저장 확인')
    }
})
[void]$form.ShowDialog()
$form.Dispose()
