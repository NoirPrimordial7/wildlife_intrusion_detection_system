$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required but was not found in PATH."
    }
}

Require-Command git

$PythonExe = $null
$PythonArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.10 --version | Out-Host
    if ($LASTEXITCODE -eq 0) {
        $PythonExe = "py"
        $PythonArgs = @("-3.10")
    }
}

if (-not $PythonExe) {
    Require-Command python
    & python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10 is required. Install Python 3.10 or make it available as py -3.10."
    }
    $PythonExe = "python"
}

Write-Host "Creating virtual environment..."
& $PythonExe @PythonArgs -m venv .venv

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Write-Host "Installing requirements..."
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt

Write-Host "Running environment checks..."
& $VenvPython scripts/check_environment.py

Write-Host "Running model smoke test..."
& $VenvPython scripts/test_model.py

Write-Host ""
Write-Host "Setup complete."
Write-Host "Launch command:"
Write-Host ".\.venv\Scripts\python.exe app/main.py"

