# CI-only. Never disable Defender, add exclusions, or execute a detected/quarantined sample.
$ErrorActionPreference = 'Stop'
$report = 'verification/windows-review/defender.json'
try {
    $status = Get-MpComputerStatus
    if (-not $status.RealTimeProtectionEnabled) { Set-MpPreference -DisableRealtimeMonitoring $false }
    # Enabling real-time protection is asynchronous on hosted Windows runners.
    $ready = $false
    for ($poll = 0; $poll -lt 24; $poll++) {
        $status = Get-MpComputerStatus
        if ($status.AMServiceEnabled -and $status.AntivirusEnabled -and $status.RealTimeProtectionEnabled) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $ready -or -not $status.AMServiceEnabled -or -not $status.AntivirusEnabled -or -not $status.RealTimeProtectionEnabled) {
        throw 'Defender is unavailable or disabled on this hosted runner. Candidate execution is blocked.'
    }
    # Hosted-runner definition downloads can fail transiently. Never substitute
    # a clean verdict or execute the candidate when all update attempts fail.
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Update-MpSignature -ErrorAction Stop
            break
        } catch {
            if ($attempt -eq 3) { throw }
            Write-Warning "Definition update failed on attempt $attempt; retrying in 10 seconds."
            Start-Sleep -Seconds 10
        }
    }
    $status = Get-MpComputerStatus
    $exe = (Resolve-Path 'verification/windows-review/candidate/Maple Private Overlay.exe').Path
    $before = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash
    $scanner = Join-Path $env:ProgramFiles 'Windows Defender/MpCmdRun.exe'
    & $scanner -Scan -ScanType 3 -File (Split-Path $exe) -DisableRemediation 2>&1 | Tee-Object -FilePath 'verification/windows-review/defender-scan.txt'
    $result = $LASTEXITCODE
    if ($result -ne 0) { throw "Defender scan did not clear the candidate (exit $result). Execution blocked." }
    if (-not (Test-Path -LiteralPath $exe)) { throw 'Executable removed/quarantined. Execution blocked.' }
    $after = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash
    if ($before -ne $after) { throw 'Executable changed during scan. Execution blocked.' }
    @{ available=$true; realtimeEnabled=$status.RealTimeProtectionEnabled; scanExit=$result; sha256=$after; engine=$status.AMEngineVersion; signatures=$status.AntivirusSignatureVersion; signatureUpdated=$status.AntivirusSignatureLastUpdated; runtimeTestCompleted=$false } | ConvertTo-Json | Set-Content $report
} catch {
    @{ available=$false; cleared=$false; reason=$_.Exception.Message; runtimeTestCompleted=$false } | ConvertTo-Json | Set-Content $report
    throw
}
