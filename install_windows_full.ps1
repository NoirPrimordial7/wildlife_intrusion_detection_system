param([switch]$CheckOnly, [switch]$NoShortcut)
$ErrorActionPreference = "Stop"
$SetupRoot = $PSScriptRoot
Set-Location -LiteralPath $SetupRoot

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Find-CompatiblePython {
    $candidates = @()
    $localEnvironment = Join-Path $SetupRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $localEnvironment) {
        $candidates += @{ Exe = $localEnvironment; Args = @() }
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    foreach ($version in @("3.12", "3.11", "3.10")) {
        if ($launcher) { $candidates += @{ Exe = $launcher.Source; Args = @("-$version") } }
        $suffix = $version.Replace(".", "")
        $known = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$suffix\python.exe"
        if (Test-Path -LiteralPath $known) { $candidates += @{ Exe = $known; Args = @() } }
        foreach ($registryRoot in @("HKCU:\Software\Python\PythonCore", "HKLM:\Software\Python\PythonCore")) {
            $key = Get-ItemProperty -LiteralPath "$registryRoot\$version\InstallPath" -ErrorAction SilentlyContinue
            if ($key -and $key.ExecutablePath) { $candidates += @{ Exe = $key.ExecutablePath; Args = @() } }
        }
    }
    foreach ($name in @("python", "python3")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { $candidates += @{ Exe = $command.Source; Args = @() } }
    }
    foreach ($candidate in $candidates) {
        try {
            $probeArgs = @($candidate.Args) + @("-c", "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12); assert sys.maxsize > 2**32; print(sys.executable)")
            $output = & $candidate.Exe @probeArgs 2>$null
            if ($LASTEXITCODE -eq 0 -and $output) { return [string]($output | Select-Object -Last 1) }
        } catch { }
    }
    return $null
}

function Test-VisualRuntime {
    $systemDirectory = Join-Path $env:SystemRoot "System32"
    foreach ($dll in @("msvcp140.dll", "msvcp140_1.dll", "vcruntime140.dll")) {
        if (-not (Test-Path -LiteralPath (Join-Path $systemDirectory $dll))) { return $false }
    }
    return $true
}

function Install-SignedDownload([string]$Url, [string]$Name, [string]$Publisher, [string[]]$InstallerArgs) {
    $download = Join-Path $SetupRoot ".setup\$Name"
    Write-Step "Downloading $Name from its official publisher"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $download -UseBasicParsing
    $signature = Get-AuthenticodeSignature -LiteralPath $download
    if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch $Publisher) {
        throw "Publisher signature could not be verified for $Name. Setup stopped."
    }
    $process = Start-Process -FilePath $download -ArgumentList $InstallerArgs -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -eq 3010) { throw "Windows requires a restart. Restart the PC and run SETUP.bat again." }
    if ($process.ExitCode -ne 0) { throw "$Name installation failed with exit code $($process.ExitCode)." }
}

function Ensure-CompatiblePython {
    $found = Find-CompatiblePython
    if ($found) { Write-Host "Compatible 64-bit Python found: $found"; return $found }
    Write-Step "Installing 64-bit Python 3.12"
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & $winget.Source install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --silent --accept-package-agreements --accept-source-agreements | Out-Host
        # Some winget results mean Python is already installed; discovery is authoritative.
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        $found = Find-CompatiblePython
        if ($found) { return $found }
        Write-Host "WinGet did not make Python available. Using the official Python installer."
    }
    Install-SignedDownload "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" "python-3.12.10-amd64.exe" "Python Software Foundation" @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "InstallLauncherAllUsers=0", "Include_test=0")
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $found = Find-CompatiblePython
    if (-not $found) { throw "Python could not be found after installation. Run SETUP.bat again or install 64-bit Python 3.12 manually." }
    return $found
}

function Create-DesktopShortcut {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) { Write-Host "Desktop folder unavailable. Use START.bat to launch."; return }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $desktop "VanRakshak Wildlife Watch.lnk"))
    $shortcut.TargetPath = Join-Path $SetupRoot "START.bat"
    $shortcut.WorkingDirectory = $SetupRoot
    $shortcut.Description = "VanRakshak Wildlife Watch"
    $shortcut.Save()
    Write-Host "Desktop shortcut created. Keep the extracted project folder in this location."
}

if ($env:OS -ne "Windows_NT" -or -not [Environment]::Is64BitOperatingSystem) {
    throw "This setup needs 64-bit Windows 10/11."
}
foreach ($file in @("launch.py", "START.bat", "requirements.txt", "models\animal_classification_model_final.h5", "data\class_names.json")) {
    if (-not (Test-Path -LiteralPath (Join-Path $SetupRoot $file))) {
        throw "Project file missing: $file. Extract the ENTIRE project ZIP before running SETUP.bat."
    }
}

if ($CheckOnly) {
    $found = Find-CompatiblePython
    Write-Host "Python: $found"
    Write-Host "Visual C++ runtime available: $(Test-VisualRuntime)"
    Write-Host "Project files: present"
    Write-Host "WinGet available: $([bool](Get-Command winget -ErrorAction SilentlyContinue))"
    if (-not $found) { throw "Python will need installation. Run SETUP.bat without -CheckOnly." }
    return
}

New-Item -ItemType Directory -Path (Join-Path $SetupRoot ".setup") -Force | Out-Null
$transcribing = $false
try {
    Start-Transcript -Path (Join-Path $SetupRoot ".setup\setup.log") -Append | Out-Null
    $transcribing = $true
    Write-Step "Checking Windows runtime"
    if (-not (Test-VisualRuntime)) {
        Write-Host "Windows may ask permission to install Microsoft's required runtime."
        Install-SignedDownload "https://aka.ms/vs/17/release/vc_redist.x64.exe" "vc_redist.x64.exe" "Microsoft Corporation" @("/install", "/quiet", "/norestart")
        if (-not (Test-VisualRuntime)) { throw "Visual C++ runtime verification failed. See .setup\setup.log." }
    }
    $pythonExe = Ensure-CompatiblePython
    Write-Step "Installing app packages and verifying the model (first setup can take several minutes)"
    & $pythonExe (Join-Path $SetupRoot "launch.py") --setup-only --verify
    if ($LASTEXITCODE -ne 0) { throw "App installation or verification failed. Fix the error above and rerun SETUP.bat." }
    if (-not $NoShortcut) { Create-DesktopShortcut }
    Write-Host "`nSetup complete. Double-click START.bat or the desktop shortcut." -ForegroundColor Green
    Write-Host "Choose Guided demo for the same walkthrough. Configure your own credentials for SMS/calls."
} catch {
    Write-Host "`nSetup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Details: .setup\setup.log. Correct the issue and rerun SETUP.bat."
    throw
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
}
