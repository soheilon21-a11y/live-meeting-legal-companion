$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$Requirements = Join-Path $BackendDir "requirements.txt"
$LiveUrl = "https://soheilon21-a11y.github.io/live-meeting-legal-companion/live/"

function Write-Step {
    param([string]$Message)
    Write-Host "[Niyosh] $Message" -ForegroundColor Cyan
}

Write-Step "Looking for Python..."

$python = $null
foreach ($candidate in @("python", "py", "python3")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        try {
            & $candidate --version *> $null
            if ($LASTEXITCODE -eq 0) {
                $python = $candidate
                break
            }
        } catch {}
    }
}

if (-not $python) {
    Write-Host "[Niyosh] ERROR: Python was not found on this machine." -ForegroundColor Red
    Write-Host "Install Python 3.12 from https://www.python.org/downloads/ and make sure it is on your PATH, then run this script again."
    exit 1
}

Write-Step "Python found ($python)."

$venvCandidates = @(
    (Join-Path $RepoRoot ".venv"),
    (Join-Path $RepoRoot "venv"),
    (Join-Path $BackendDir ".venv"),
    (Join-Path $BackendDir "venv")
)

$venv = $null
foreach ($candidate in $venvCandidates) {
    if (Test-Path (Join-Path $candidate "Scripts\python.exe")) {
        $venv = $candidate
        break
    }
}

$needsInstall = $false

if ($venv) {
    Write-Step "Using existing virtual environment: $venv"
    $venvPython = Join-Path $venv "Scripts\python.exe"
    & $venvPython -c "import fastapi, uvicorn" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Packages are missing - installing requirements."
        $needsInstall = $true
    } else {
        Write-Step "Packages are already installed - skipping pip install."
    }
} else {
    $venv = Join-Path $RepoRoot ".venv"
    Write-Step "Creating virtual environment: $venv"
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Niyosh] ERROR: Failed to create the virtual environment." -ForegroundColor Red
        exit 1
    }
    $venvPython = Join-Path $venv "Scripts\python.exe"
    $needsInstall = $true
}

if ($needsInstall) {
    & $venvPython -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Niyosh] ERROR: pip install failed. Check your internet connection and try again." -ForegroundColor Red
        exit 1
    }
    Write-Step "Requirements installed."
}

Write-Step "Starting the backend on http://127.0.0.1:8002 ..."
Start-Process -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8002") -WorkingDirectory $BackendDir

Write-Step "Waiting for the backend to become ready..."
$up = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $up = $true
            break
        }
    } catch {}
}

if ($up) {
    Write-Step "Backend is up at http://127.0.0.1:8002"
} else {
    Write-Host "[Niyosh] WARNING: the backend did not answer on http://127.0.0.1:8002/health yet. Check the backend window for errors, then click Re-check connection on the page." -ForegroundColor Yellow
}

Write-Step "Opening the Live Analysis control panel..."
Start-Process $LiveUrl

Write-Step "Done. Keep the backend window open; closing it stops Niyosh."
