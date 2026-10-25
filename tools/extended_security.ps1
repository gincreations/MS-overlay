# Runs only on disposable GitHub-hosted Windows; never disables protection.
$ErrorActionPreference = 'Stop'
$base = (Resolve-Path 'verification/extended-security').Path
$tag=$env:REVIEW_TAG
if ($tag -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+(-rc[0-9]+)?$') { throw 'Invalid review tag' }
$expected=$env:REVIEW_ZIP_SHA256
$expectedExe=$env:REVIEW_EXE_SHA256
if ($expected -notmatch '^[a-f0-9]{64}$' -or $expectedExe -notmatch '^[a-f0-9]{64}$') { throw 'Pinned candidate hashes required' }
$zip = Join-Path $base ('Maple-Private-Overlay-' + $tag.Substring(1) + '-portable.zip')
if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'Release hash mismatch' }
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $base 'unpacked')
$app = Join-Path $base 'unpacked/Maple Private Overlay'
$exe = Join-Path $app 'Maple Private Overlay.exe'
$status = Get-MpComputerStatus
$status | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AMRunningMode | ConvertTo-Json | Set-Content (Join-Path $base 'defender-initial.json')
# Hosted images may start with realtime monitoring off. Enable protection, never weaken it.
if (-not $status.RealTimeProtectionEnabled) {
    Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction Stop
}
for ($poll=0; $poll -lt 24; $poll++) {
    $status = Get-MpComputerStatus
    if ($status.AMServiceEnabled -and $status.AntivirusEnabled -and $status.RealTimeProtectionEnabled) { break }
    Start-Sleep -Seconds 5
}
$status | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AMRunningMode | ConvertTo-Json | Set-Content (Join-Path $base 'defender-before-runtime.json')
if (-not $status.AMServiceEnabled -or -not $status.AntivirusEnabled -or -not $status.RealTimeProtectionEnabled) { throw 'Enabled Defender including realtime protection required' }
for ($attempt=1; $attempt -le 3; $attempt++) {
    try { Update-MpSignature -ErrorAction Stop; break }
    catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 10 }
}
$scanner = Join-Path $env:ProgramFiles 'Windows Defender/MpCmdRun.exe'
& $scanner -Scan -ScanType 3 -File $app -DisableRemediation
if ($LASTEXITCODE -ne 0) { throw 'Defender did not clear exact runtime; execution blocked' }
if ((Get-FileHash $exe -Algorithm SHA256).Hash.ToLower() -ne $expectedExe) { throw 'EXE changed' }
# Obtain Microsoft-signed monitoring tool, before trace begins.
Invoke-WebRequest 'https://download.sysinternals.com/files/ProcessMonitor.zip' -OutFile (Join-Path $base 'procmon.zip')
Expand-Archive (Join-Path $base 'procmon.zip') (Join-Path $base 'monitor')
$procmon = Join-Path $base 'monitor/Procmon64.exe'
$sig = Get-AuthenticodeSignature $procmon
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Procmon signature invalid' }
# Native dependency identity: do not trust filenames as version evidence.
$native = @()
Get-ChildItem (Join-Path $app 'tesseract') -File | Where-Object { $_.Extension -in '.exe','.dll' } | ForEach-Object {
  $v=$_.VersionInfo
  $native += @{ file=$_.Name; sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(); product=$v.ProductName; productVersion=$v.ProductVersion; fileVersion=$v.FileVersion }
}
$native | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $base 'ocr-native-inventory.json')
& (Join-Path $app 'tesseract/tesseract.exe') --version 2>&1 | Out-File (Join-Path $base 'ocr-version-summary.txt')
if ($LASTEXITCODE -ne 0) { throw 'Bundled OCR version check failed' }
# Source/helper probe uses exact packaged source, not a rewritten substitute.
Expand-Archive (Join-Path $app 'Maple-Private-Overlay-source.zip') (Join-Path $base 'source')
$cwd = Join-Path $base 'untrusted-working-directory'
$testProfile = Join-Path $base 'dummy-home'
New-Item -ItemType Directory -Force $cwd,$testProfile | Out-Null
$oldProfile=$env:USERPROFILE; $oldAppData=$env:APPDATA; $oldLocal=$env:LOCALAPPDATA
$env:USERPROFILE=$testProfile; $env:APPDATA=Join-Path $testProfile 'AppData/Roaming'; $env:LOCALAPPDATA=Join-Path $testProfile 'AppData/Local'
$env:MAPLE_EXP_DATA=Join-Path $testProfile 'overlay-data'
$env:MAPLE_SECURITY_MARKER=Join-Path $base 'helper-canary-hit.txt'
# No actual secrets: bait checks identify attempted accesses only.
foreach ($relative in @('AppData/Local/Google/Chrome/User Data/Default/Login Data','AppData/Local/Google/Chrome/User Data/Local State','AppData/Roaming/Exodus/exodus.wallet/canary.txt','AppData/Roaming/Electrum/wallets/default_wallet')) {
  $f=Join-Path $testProfile $relative; New-Item -ItemType Directory -Force (Split-Path $f) | Out-Null
  Set-Content -LiteralPath $f -Value 'SYNTHETIC SECURITY TEST DATA - NOT A REAL PASSWORD OR WALLET'
}
# Copy signed system DLLs as harmless search-order probes; no custom DLL payload.
foreach ($dll in @('version.dll','winmm.dll','dbghelp.dll')) { Copy-Item (Join-Path $env:SystemRoot "System32/$dll") (Join-Path $cwd $dll) }
$cs = Join-Path $base 'Canary.cs'
@'
using System; using System.IO;
class Canary { static int Main() { File.WriteAllText(Environment.GetEnvironmentVariable("MAPLE_SECURITY_MARKER"), "benign explorer search-path probe executed"); return 0; } }
'@ | Set-Content $cs
$csc = Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
& $csc /nologo /target:exe "/out:$cwd/explorer.exe" $cs
if ($LASTEXITCODE -ne 0) { throw 'Could not compile benign helper canary' }
# Scan benign probes too; no exclusions even for test fixtures.
& $scanner -Scan -ScanType 3 -File $cwd -DisableRemediation
if ($LASTEXITCODE -ne 0) { throw 'Probe scan failed' }
$pml=Join-Path $base 'trace.pml'; $csv=Join-Path $base 'trace.csv'
$roots=@();$setupExit=$null;$normalStarted=$false;$probeExit=$null;$originalCanary=$false;$fixedCanary=$null;$fixedProbeExit=$null;$ocrExit=$null;$ocrText=$null
$monitorArgs="/AcceptEula /Quiet /Minimized /BackingFile `"$pml`""
Start-Process -FilePath $procmon -ArgumentList $monitorArgs | Out-Null
Start-Sleep -Seconds 3
try {
  $p=Start-Process -FilePath $exe -ArgumentList '--check-setup' -WorkingDirectory $cwd -PassThru
  $roots += @{pid=$p.Id; phase='packaged-setup'}
  if (-not $p.WaitForExit(120000)) { Stop-Process -Id $p.Id -Force; throw 'Setup timeout' }
  $p.Refresh();$setupExit=$p.ExitCode
  if ($setupExit -ne 0) { throw "Packaged setup failed: $setupExit" }
  $p=Start-Process -FilePath $exe -WorkingDirectory $cwd -PassThru
  $roots += @{pid=$p.Id; phase='normal-startup'}
  Start-Sleep -Seconds 20
  $p.Refresh();$normalStarted=-not $p.HasExited
  if (-not $p.HasExited) { $null=$p.CloseMainWindow(); if (-not $p.WaitForExit(10000)) { Stop-Process -Id $p.Id -Force } }
  # Exercise the exact OCR binary under the same trace using only synthetic text.
  Add-Type -AssemblyName System.Drawing
  $bitmap = [System.Drawing.Bitmap]::new(600,90)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $font = [System.Drawing.Font]::new('Arial',32)
  try {
    $graphics.Clear([System.Drawing.Color]::White)
    $graphics.DrawString('1234567890',$font,[System.Drawing.Brushes]::Black,20,15)
    $ocrInput = Join-Path $base 'synthetic-ocr.png'
    $bitmap.Save($ocrInput,[System.Drawing.Imaging.ImageFormat]::Png)
  } finally { $font.Dispose(); $graphics.Dispose(); $bitmap.Dispose() }
  $env:TESSDATA_PREFIX=Join-Path $app 'tesseract/tessdata'
  $ocrOut=Join-Path $base 'synthetic-ocr-output.txt'
  $ocrArgs='"'+$ocrInput+'" stdout --psm 7 -c tessedit_char_whitelist=0123456789'
  $p=Start-Process -FilePath (Join-Path $app 'tesseract/tesseract.exe') -ArgumentList $ocrArgs -WorkingDirectory $cwd -RedirectStandardOutput $ocrOut -PassThru
  $roots += @{pid=$p.Id; phase='bundled-ocr-synthetic-crop'}
  if (-not $p.WaitForExit(30000)) { Stop-Process -Id $p.Id -Force; throw 'OCR trace timeout' }
  $p.Refresh();$ocrExit=$p.ExitCode;$ocrText=(Get-Content $ocrOut -Raw).Trim()
  if ($ocrExit -ne 0 -or $ocrText -ne '1234567890') { throw 'Traced OCR recognition failed' }
  $probe=Join-Path $base 'helper-probe.py'
@'
import os,sys,time
sys.path.insert(0,sys.argv[1])
from platforms.windows import WindowsPlatform
WindowsPlatform().show_file(sys.argv[2])
time.sleep(2)
'@ | Set-Content $probe
  $python=(Get-Command python).Source
  $arguments='"'+$probe+'" "'+(Join-Path $base 'source')+'" "'+(Join-Path $testProfile 'dummy.png')+'"'
  $p=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $cwd -PassThru
  $roots += @{pid=$p.Id; phase='source-helper-search-probe'}
  if (-not $p.WaitForExit(15000)) { Stop-Process -Id $p.Id -Force; throw 'Helper probe timeout' }
  $p.Refresh();$probeExit=$p.ExitCode
  $originalCanary=Test-Path $env:MAPLE_SECURITY_MARKER
  if ($tag -ne 'v0.1.18-rc2' -and ($probeExit -ne 0 -or $originalCanary)) { throw 'Packaged helper search-path regression failed' }
  $env:MAPLE_SECURITY_MARKER=Join-Path $base 'fixed-helper-canary-hit.txt'
  $arguments='"'+$probe+'" "'+$env:GITHUB_WORKSPACE+'" "'+(Join-Path $testProfile 'dummy.png')+'"'
  $p=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $cwd -PassThru
  $roots += @{pid=$p.Id; phase='fixed-source-helper-search-probe'}
  if (-not $p.WaitForExit(15000)) { Stop-Process -Id $p.Id -Force; throw 'Fixed helper probe timeout' }
  $p.Refresh();$fixedProbeExit=$p.ExitCode
  $fixedCanary=Test-Path $env:MAPLE_SECURITY_MARKER
  if ($fixedProbeExit -ne 0 -or $fixedCanary) { throw 'Fixed helper search-path regression failed' }
} finally {
  Start-Process -FilePath $procmon -ArgumentList '/Terminate /Quiet' -Wait | Out-Null
  $env:USERPROFILE=$oldProfile;$env:APPDATA=$oldAppData;$env:LOCALAPPDATA=$oldLocal
  $status=Get-MpComputerStatus
  @{releaseTag=$tag;zipSHA256=$expected;exeSHA256=$expectedExe;roots=$roots;setupExit=$setupExit;ocrExit=$ocrExit;ocrText=$ocrText;normalStartupSurvived20Seconds=$normalStarted;helperProbeExit=$probeExit;helperCanaryExecuted=$originalCanary;fixedHelperCanaryExecuted=$fixedCanary;fixedHelperProbeExit=$fixedProbeExit;defenderEnabled=$status.AntivirusEnabled;realTimeProtectionEnabled=$status.RealTimeProtectionEnabled;signatures=$status.AntivirusSignatureVersion;procmonSigner=$sig.SignerCertificate.Subject;boundedTraceOnly=$true} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $base 'runtime-observation.json')
}
Start-Process -FilePath $procmon -ArgumentList "/AcceptEula /Quiet /OpenLog `"$pml`" /SaveAs `"$csv`"" -Wait | Out-Null
if (-not (Test-Path $csv)) { throw 'Procmon CSV missing; no behavioral conclusion allowed' }
