$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$Requirements = Join-Path $BackendDir "requirements.txt"
$LiveUrl = "https://soheilon21-a11y.github.io/live-meeting-legal-companion/live/"
$VenvDir = Join-Path $env:LOCALAPPDATA "Niyosh\venv312"
$Port = 8002

function Write-Step { param([string]$Message) Write-Host "[Niyosh] $Message" -ForegroundColor Cyan }
function Write-Err  { param([string]$Message) Write-Host "[Niyosh] ERROR: $Message" -ForegroundColor Red }
function Write-Warn { param([string]$Message) Write-Host "[Niyosh] WARNING: $Message" -ForegroundColor Yellow }

# ---- Resolve a Python 3.12 interpreter (full path) ----
function Resolve-Python312 {
    # 1) Windows py launcher with an explicit 3.12 request.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe }
    }
    # 2) python / python3 on PATH - verify the actual version.
    foreach ($name in @("python", "python3")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $exe = & $name -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) {
                $ver = & $exe -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $ver -match "3\s+12") { return $exe }
            }
        }
    }
    return $null
}

function Get-PortOwner {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return $null }
    return [int]$conn.OwningProcess
}

function Get-ProcessChainCommandLines {
    param([int]$Pid)
    $lines = @()
    $seen = @{}
    $current = $Pid
    for ($i = 0; $i -lt 12; $i++) {
        if (-not $current -or $seen.ContainsKey($current)) { break }
        $seen[$current] = $true
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$current" -ErrorAction SilentlyContinue
        if (-not $proc) { break }
        if ($proc.CommandLine) { $lines += $proc.CommandLine }
        $current = [int]$proc.ParentProcessId
    }
    return $lines
}

# ---- Fake-ASR guard: fail closed, never let a test-only setting reach prod ----
# NIYOSH_E2E_FAKE_ASR must only ever activate the Fake-ASR used by the isolated
# e2e harness (website/e2e/run-e2e.mjs). If it is present in this launcher's
# environment — even as "0" or an empty string — refuse to start.
if (Test-Path "Env:NIYOSH_E2E_FAKE_ASR") {
    Write-Err "NIYOSH_E2E_FAKE_ASR is set in this environment (value: '$env:NIYOSH_E2E_FAKE_ASR')."
    Write-Err "Fake-ASR is a test-only setting and must not reach the real application launcher."
    Write-Host "Unset it with:  Remove-Item Env:NIYOSH_E2E_FAKE_ASR" -ForegroundColor Gray
    Write-Host "Then run this script again." -ForegroundColor Gray
    exit 1
}

# ---- Locate Python 3.12 ----
Write-Step "Looking for Python 3.12..."
$python = Resolve-Python312
if (-not $python) {
    Write-Err "Python 3.12 was not found on this machine."
    Write-Host "Niyosh requires Python 3.12. Install it from https://www.python.org/downloads/ and ensure 'py' is on your PATH, then run this script again." -ForegroundColor Gray
    exit 1
}
Write-Step "Using Python 3.12: $python"

# ---- Prepare the virtual environment (user-local, never the repo .venv) ----
$venvPython = Join-Path $VenvDir "Scripts\python.exe"
if (Test-Path $venvPython) {
    $existing = & $venvPython -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
    if (-not ($existing -match "3\s+12")) {
        Write-Err "Existing environment at '$VenvDir' is not Python 3.12 (got: $existing)."
        Write-Err "Refusing to reuse or overwrite it. Remove or rename it, then re-run this script."
        exit 1
    }
    Write-Step "Using existing virtual environment: $VenvDir"
} else {
    Write-Step "Creating virtual environment: $VenvDir"
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to create the virtual environment."
        exit 1
    }
}

# ---- Install pinned requirements only when the installed versions do not match ----
# Import success alone does not prove the pinned versions are installed, so we
# compare each `name==version` line against the installed distributions first.
$checkScript = Join-Path $PSScriptRoot "check_requirements.py"
& $venvPython $checkScript $Requirements *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Installing/aligning pinned requirements..."
    & $venvPython -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install failed. Check your connection and the log above."
        exit 1
    }
} else {
    Write-Step "Pinned requirements already satisfied - skipping pip install."
}

# ---- Dependency consistency check (fail closed) ----
Write-Step "Checking package consistency (pip check)..."
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) {
    Write-Err "pip check reported dependency inconsistencies."
    Write-Host "Niyosh will not start with an inconsistent environment." -ForegroundColor Gray
    Write-Host "To recover, recreate the environment:" -ForegroundColor Gray
    Write-Host "  1. Delete $VenvDir" -ForegroundColor Gray
    Write-Host "  2. Re-run this script (it will rebuild the venv and reinstall pinned requirements)." -ForegroundColor Gray
    exit 1
}

# ---- Port guard: never start a duplicate, never kill an existing process ----
$owner = Get-PortOwner $Port
if ($owner) {
    # Command-line ancestry cannot reliably reveal a process's inherited
    # environment, so marker strings below are only a heuristic, not proof.
    $chain = Get-ProcessChainCommandLines $owner
    $testMarkerSeen = $false
    foreach ($line in $chain) {
        if ($line -match "NIYOSH_E2E_FAKE_ASR|e2e-data|niyosh-stage2") { $testMarkerSeen = $true }
    }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
    $procName = if ($proc) { $proc.Name } else { "unknown" }
    if ($testMarkerSeen) {
        Write-Warn "A process already listening on port $Port (PID $owner, $procName) has command-line markers that SUGGEST a test/E2E backend (Fake ASR). This cannot be confirmed from the command line alone."
    } else {
        Write-Warn "A process is already listening on port $Port (PID $owner, $procName). It could not be classified as a normal or test backend from the command line alone."
    }
    Write-Host "[Niyosh] Refusing to start a duplicate backend. No process was killed." -ForegroundColor Gray
    exit 0
}

# ---- Start the backend with an explicit, predictable data directory ----
$DataDir = Join-Path $BackendDir "data"
$env:DATA_DIR = $DataDir
Write-Step "Using data directory: $DataDir"
Write-Step "Starting the backend on http://127.0.0.1:$Port ..."
Start-Process -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$Port") -WorkingDirectory $BackendDir

Write-Step "Waiting for the backend to become ready..."
$up = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $up = $true
            break
        }
    } catch {}
}

if ($up) {
    Write-Step "Backend is up at http://127.0.0.1:$Port"
} else {
    Write-Warn "The backend did not answer on http://127.0.0.1:$Port/health yet. Check the backend window for errors, then click Re-check connection on the page."
}

Write-Step "Opening the Live Analysis control panel..."
Start-Process $LiveUrl

Write-Step "Done. Keep the backend window open; closing it stops Niyosh."
