$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$AppName = "VanRakshak AI Wildlife Monitoring System"
$PythonVersion = "3.10"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Require-Windows {
    if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
        throw "This installer is for Windows only."
    }
}

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WithWinget($Id, $Name) {
    if (-not (Test-Command winget)) {
        throw "$Name is missing and winget was not found. Install $Name manually, then run this installer again."
    }
    Write-Step "Installing $Name"
    winget install --id $Id --scope user --silent --accept-package-agreements --accept-source-agreements
}

function Ensure-Git {
    if (Test-Command git) {
        Write-Host "Git found."
        return
    }
    Install-WithWinget "Git.Git" "Git"
    if (-not (Test-Command git)) {
        throw "Git installation finished, but git is not available in this terminal. Close this window and run install_windows_full.bat again."
    }
}

function Ensure-Python310 {
    if (Test-Command py) {
        py -3.10 --version | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Python 3.10 found."
            return
        }
    }

    Install-WithWinget "Python.Python.3.10" "Python 3.10"
    if (-not (Test-Command py)) {
        throw "Python launcher is not available yet. Close this window and run install_windows_full.bat again."
    }
    py -3.10 --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10 installation did not become available. Restart Windows or run the installer again."
    }
}

function Reset-LocalSecrets {
    $smsConfig = Join-Path $PSScriptRoot "data\sms_config.json"
    if (Test-Path $smsConfig) {
        Write-Host "Leaving existing local data\sms_config.json in place. It is ignored by Git."
    } else {
        Write-Host "SMS config not present. App will create disabled config on first run."
    }
}

function Install-PythonDependencies {
    Write-Step "Creating virtual environment"
    if (-not (Test-Path ".venv")) {
        py -3.10 -m venv .venv
    }

    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Virtual environment was not created correctly."
    }

    Write-Step "Installing Python packages"
    & $python -m pip install --upgrade pip setuptools wheel
    & $python -m pip install -r requirements.txt
}

function Prepare-YoloWeights {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    Write-Step "Preparing YOLO model weights"
    & $python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); print('YOLO weights ready')"
}

function Run-Verification {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    Write-Step "Running environment check"
    & $python scripts\check_environment.py

    Write-Step "Running model smoke test"
    & $python scripts\test_model.py

    Write-Step "Checking hybrid evaluator help"
    & $python scripts\evaluate_hybrid_on_video.py --help | Out-Null
}

function Create-LaunchFiles {
    $pythonw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    $main = Join-Path $PSScriptRoot "app\main.py"
    $bat = Join-Path $PSScriptRoot "Run_VanRakshak.bat"

    Write-Step "Creating launcher files"
    @"
@echo off
cd /d "%~dp0"
".\.venv\Scripts\python.exe" app\main.py
pause
"@ | Set-Content -Path $bat -Encoding ASCII

    if (Test-Path $pythonw) {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $shortcutPath = Join-Path $desktop "VanRakshak AI Wildlife Monitoring System.lnk"
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $pythonw
        $shortcut.Arguments = "`"$main`""
        $shortcut.WorkingDirectory = $PSScriptRoot
        $shortcut.Description = $AppName
        $shortcut.Save()
        Write-Host "Desktop shortcut created: $shortcutPath"
    } elseif (Test-Path $python) {
        Write-Host "pythonw.exe not found; use Run_VanRakshak.bat."
    }
}

function Print-FinalInstructions {
    Write-Host ""
    Write-Host "Setup complete." -ForegroundColor Green
    Write-Host ""
    Write-Host "Run the app:"
    Write-Host "  Double-click the desktop shortcut"
    Write-Host "  OR run: .\Run_VanRakshak.bat"
    Write-Host ""
    Write-Host "SMS is disabled by default. Do not add real SMS credentials unless you are ready to test paid/trial SMS."
}

Require-Windows
Write-Step "Checking system requirements"
Ensure-Git
Ensure-Python310
Reset-LocalSecrets
Install-PythonDependencies
Prepare-YoloWeights
Run-Verification
Create-LaunchFiles
Print-FinalInstructions
