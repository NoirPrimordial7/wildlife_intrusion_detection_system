# Verifies installer control flow with mocked downloads/processes; installs nothing.
$ErrorActionPreference = "Stop"
$installer = Join-Path (Split-Path $PSScriptRoot -Parent) "install_windows_full.ps1"
. $installer -CheckOnly
$signedInstaller = (Get-Command Install-SignedDownload).ScriptBlock
function Assert-Setup($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$script:probe = 0
$script:downloads = 0
$script:wingetRuns = 0
$script:scenario = "existing"
function Find-CompatiblePython {
    $script:probe++
    switch ($script:scenario) {
        "existing" { return "C:\existing python\python.exe" }
        "winget" { if ($script:probe -gt 1) { return "C:\winget python\python.exe" } }
        "fallback" { if ($script:probe -gt 2) { return "C:\fallback python\python.exe" } }
        "no-winget" { if ($script:probe -gt 1) { return "C:\fallback python\python.exe" } }
    }
    return $null
}
function Get-Command($Name, $ErrorAction) {
    if ($Name -eq "winget") {
        if ($script:scenario -eq "no-winget") { return $null }
        return @{ Source = "Invoke-FakeWinget" }
    }
    return Microsoft.PowerShell.Core\Get-Command $Name -ErrorAction SilentlyContinue
}
function Invoke-FakeWinget {
    $script:wingetRuns++
    Write-Output "Mock installation progress"
    $global:LASTEXITCODE = 0
}
function Install-SignedDownload($Url, $Name, $Publisher, $InstallerArgs) {
    $script:downloads++
    Assert-Setup ($Url -like "https://www.python.org/*") "Python fallback must use the official publisher"
    Assert-Setup ($Publisher -eq "Python Software Foundation") "Python publisher check is missing"
}
foreach ($scenario in @("existing", "winget", "fallback", "no-winget", "failed")) {
    $script:scenario = $scenario
    $script:probe = 0
    $script:downloads = 0
    $script:wingetRuns = 0
    if ($scenario -eq "failed") {
        $failed = $false
        try { Ensure-CompatiblePython | Out-Null } catch { $failed = $true }
        Assert-Setup $failed "Unsuccessful installation must stop setup"
        continue
    }
    $result = @(Ensure-CompatiblePython)
    Assert-Setup ($result.Count -eq 1 -and $result[0] -like "C:\*python.exe") "Installer must return only the Python path, without capturing package-manager output"
    if ($scenario -eq "existing") { Assert-Setup ($script:wingetRuns -eq 0 -and $script:downloads -eq 0) "Existing Python should skip installation" }
    if ($scenario -in @("fallback", "no-winget")) { Assert-Setup ($script:downloads -eq 1) "Python fallback was not used" }
}

# Exercise signature checks, executable error codes, restart handling and hidden launch.
Set-Item Function:\Install-SignedDownload $signedInstaller
$script:signatureStatus = "Valid"
$script:publisher = "CN=Python Software Foundation"
$script:processCode = 0
$script:processRuns = 0
function Invoke-WebRequest($Uri, $OutFile, [switch]$UseBasicParsing) { }
function Get-AuthenticodeSignature($LiteralPath) {
    return @{ Status = $script:signatureStatus; SignerCertificate = @{ Subject = $script:publisher } }
}
function Start-Process($FilePath, $ArgumentList, $WindowStyle, [switch]$PassThru, [switch]$Wait) {
    Assert-Setup ($WindowStyle -eq "Hidden") "Installer helper should launch hidden"
    $script:processRuns++
    return @{ ExitCode = $script:processCode }
}
foreach ($case in @("valid", "invalid-signature", "wrong-publisher", "failed-process", "restart")) {
    $script:signatureStatus = if ($case -eq "invalid-signature") { "NotSigned" } else { "Valid" }
    $script:publisher = if ($case -eq "wrong-publisher") { "CN=Wrong Publisher" } else { "CN=Python Software Foundation" }
    $script:processCode = if ($case -eq "failed-process") { 1 } elseif ($case -eq "restart") { 3010 } else { 0 }
    $script:processRuns = 0
    $failed = $false
    try { Install-SignedDownload "https://www.python.org/mock.exe" "mock.exe" "Python Software Foundation" @("/quiet") } catch { $failed = $true }
    Assert-Setup ($failed -eq ($case -ne "valid")) "Incorrect signed-installer result: $case"
    if ($case -in @("invalid-signature", "wrong-publisher")) { Assert-Setup ($script:processRuns -eq 0) "Unverified binary must never execute" }
}
Write-Host "PASS: existing Python, WinGet install, signed fallback, absent WinGet, failure/retry handling, publisher verification, process exit codes and restart handling. No software installed."
