# install-windows.ps1
# Hermes Dist — Windows installer (cross-OS-aware rewrite for v0.3.0).
#
# Usage (in PowerShell, elevated recommended for Task Scheduler registration):
#   .\install-windows.ps1 -RelayUrl "https://relay.your-domain" -DistRepo "https://github.com/you/hermes-dist"
#
# Or with defaults (registers with localhost relay for testing):
#   .\install-windows.ps1
#
# What this does:
#   1. Refuses to run on non-Windows hosts (safety check)
#   2. Verifies prerequisites (python, git, schtasks.exe)
#   3. Sets HERMES_HOME=$env:USERPROFILE\.hermes  and  WORKING_DIR=$env:USERPROFILE\Documents
#   4. Installs Hermes Agent via the official PowerShell installer (irm)
#   5. Clones the hermes-dist repo (or uses local path)
#   6. Runs .onboard.sh via Git Bash
#   7. Registers a Windows Task Scheduler task for the daily 09:00 update check
#   8. Registers a Windows Task Scheduler task for the 60s heartbeat
#
# Environment / parameter overrides:
#   -HermesHome    default: Join-Path $env:USERPROFILE ".hermes"
#   -WorkingDir    default: Join-Path $env:USERPROFILE "Documents"
#   -DistRepo      default: ""  (must be set OR bundle must already exist locally)
#   -RelayUrl      default: "https://relay.local"
#   -HermesBin     default: "$HermesHome\venv\Scripts\hermes.exe"
#   -SkipScheduler switch   do not register Task Scheduler tasks
#   -SkipHeartbeat switch   do not register the heartbeat task
#   -Unregister    switch   tear down any previously-registered Hermes Dist tasks
#
# Verified on: Windows 10 21H2+, Windows 11 22H2+, Windows Server 2019+
# Requires: PowerShell 5.1+ (ships with Windows 10+), Git for Windows (bash.exe).
# Note: Task Scheduler registration typically requires elevation. If unelevated,
# the script logs a warning and continues; the user can re-run as admin.

[CmdletBinding()]
param(
    [string]$RelayUrl = "https://relay.local",
    [string]$DistRepo = "",
    [string]$HermesHome = (Join-Path $env:USERPROFILE ".hermes"),
    [string]$WorkingDir = (Join-Path $env:USERPROFILE "Documents"),
    [string]$HermesBin = "",
    [switch]$SkipScheduler,
    [switch]$SkipHeartbeat,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

# ─── 0. OS guard ──────────────────────────────────────────────────────────
# Per skill cross-platform-bash-scripting §2 (Windows/msys branch): detect first.
if (-not $IsWindows -and -not ($env:OS -eq "Windows_NT")) {
    Write-Host "✗ install-windows.ps1 must be run on Windows." -ForegroundColor Red
    Write-Host "  On macOS use install-macos.sh; on Linux use install-linux.sh." -ForegroundColor Red
    exit 1
}

# ─── 1. HermesBin default (after we know $HermesHome is set) ───────────────
if ([string]::IsNullOrEmpty($HermesBin)) {
    $HermesBin = Join-Path $HermesHome "venv\Scripts\hermes.exe"
}

# ─── 2. Banner + prerequisite check ───────────────────────────────────────
Write-Host "=== Hermes Dist — Windows Installer (v0.3.0) ===" -ForegroundColor Cyan
Write-Host ""

$prereqs = @(
    @{ name = "Python 3.11+"; check = { & python --version 2>&1 | Select-String "Python 3\.(1[1-9]|[2-9]\d)" } },
    @{ name = "Git";          check = { & git --version 2>&1 } },
    @{ name = "schtasks.exe"; check = { & schtasks /? 2>&1 | Select-String "schtasks" } },
    @{ name = "Docker (optional, for tinysearch)"; check = { & docker --version 2>&1 }; optional = $true }
)

foreach ($p in $prereqs) {
    try {
        $result = & $p.check
        if ($result) {
            Write-Host "  ✓ $($p.name): $result" -ForegroundColor Green
        } elseif ($p.optional) {
            Write-Host "  ⚠ $($p.name): not found (optional)" -ForegroundColor Yellow
        } else {
            throw "$($p.name) not found"
        }
    } catch {
        Write-Host "  ✗ $($p.name): not found" -ForegroundColor Red
        if (-not $p.optional) {
            Write-Host "    Install from https://www.python.org/downloads/ and https://git-scm.com/download/win" -ForegroundColor Yellow
            exit 1
        }
    }
}

# ─── 3. Path resolution (Windows) ─────────────────────────────────────────
# Per skill cross-platform-bash-scripting P1+P5 + P13: HERMES_HOME is at
# $env:USERPROFILE\.hermes (the legacy convention preserved here for Windows
# to match the .onboard.sh that lives in the bundle). WORKING_DIR defaults to
# the user's Documents folder. NO literal "C:\Users\somew\..." paths.
Write-Host ""
Write-Host "  HERMES_HOME: $HermesHome"
Write-Host "  WORKING_DIR: $WorkingDir"
Write-Host "  HERMES_BIN:  $HermesBin"
Write-Host ""

# ─── 4. Unregister path (early exit if user just wants to tear down) ──────
$UpdateTaskName   = "HermesDistUpdateCheck"
$HeartbeatTaskName = "HermesDistHeartbeat"

if ($Unregister) {
    foreach ($t in @($UpdateTaskName, $HeartbeatTaskName)) {
        $existing = & schtasks /Query /TN $t 2>$null
        if ($LASTEXITCODE -eq 0) {
            & schtasks /Delete /TN $t /F | Out-Null
            Write-Host "  ✓ Unregistered task: $t" -ForegroundColor Green
        } else {
            Write-Host "  - Task not registered: $t" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
    Write-Host "=== Unregistration Complete ===" -ForegroundColor Cyan
    exit 0
}

# ─── 5. Install Hermes Agent if not present ───────────────────────────────
if (-not (Get-Command hermes -ErrorAction SilentlyContinue) -and -not (Test-Path $HermesBin)) {
    Write-Host ""
    Write-Host "Installing Hermes Agent via official installer..."
    # Official PowerShell one-liner. NOSPAM=1 keeps the post-install banner quiet.
    $env:NOSPAM = "1"
    $installScript = irm "https://hermes-agent.nousresearch.com/install.ps1"
    Invoke-Expression $installScript
} else {
    Write-Host "  ✓ Hermes Agent already installed" -ForegroundColor Green
}

# ─── 6. Clone (or reuse) hermes-dist repo ─────────────────────────────────
$DIST_DIR = Join-Path (Split-Path $HermesHome -Parent) "hermes-dist"
if (Test-Path (Join-Path $DIST_DIR ".git")) {
    Write-Host "  ✓ Using existing $DIST_DIR" -ForegroundColor Green
} else {
    if ($DistRepo) {
        Write-Host "Cloning $DistRepo to $DIST_DIR ..."
        & git clone $DistRepo $DIST_DIR
        if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
    } else {
        Write-Host "  ✗ No -DistRepo specified and no local hermes-dist found." -ForegroundColor Red
        Write-Host "    Either specify -DistRepo or copy the hermes-dist folder to $DIST_DIR manually." -ForegroundColor Red
        exit 1
    }
}

# ─── 7. Run .onboard.sh via Git Bash ──────────────────────────────────────
# Per skill cross-platform-bash-scripting P10: use a Get-BashExe helper rather
# than a literal "bash.exe" path.
function Get-BashExe {
    $cmd = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:ProgramFiles "Git\bin\bash.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Git\bin\bash.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Git\bin\bash.exe")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

$bash = Get-BashExe
if (-not $bash) {
    Write-Host "  ✗ bash.exe not found. Install Git for Windows." -ForegroundColor Red
    exit 1
}
$OnboardScript = Join-Path $DIST_DIR ".onboard.sh"
if (-not (Test-Path $OnboardScript)) {
    Write-Host "  ✗ .onboard.sh not found in $DIST_DIR" -ForegroundColor Red
    exit 1
}

# Convert HERMES_HOME to a path the bash subprocess can consume (Windows-native form
# for $HOME — MSYS will translate to /c/... itself).
$env:HERMES_HOME     = $HermesHome
$env:WORKING_DIR     = $WorkingDir
$env:HERMES_DIST_REPO = $DistRepo
$env:HERMES_RELAY_URL = $RelayUrl

Write-Host ""
Write-Host "Running .onboard.sh ..."
& $bash $OnboardScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ .onboard.sh failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# ─── 8. Start tinysearch Docker container if Docker is available ─────────
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "Starting tinysearch Docker container..."
    $existing = & docker ps -a --filter "name=hermes-tinysearch" --format "{{.Names}}" 2>$null
    if ($existing -eq "hermes-tinysearch") {
        & docker start hermes-tinysearch 2>$null | Out-Null
    } else {
        & docker pull hermes/tinysearch:latest 2>$null | Out-Null
        & docker run -d --name hermes-tinysearch -p 127.0.0.1:8000:8000 --restart unless-stopped hermes/tinysearch:latest 2>$null | Out-Null
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ tinysearch running at http://127.0.0.1:8000" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ tinysearch failed to start. Web scraping will fall back to direct HTTP." -ForegroundColor Yellow
    }
}

# ─── 9. Register Windows Task Scheduler: daily 09:00 update check ─────────
# We use schtasks.exe directly (NOT Register-ScheduledTask cmdlet) because
# schtasks handles elevation/principal quietly and the XML escape rules for
# the cmdlet are a known footgun (see skill hermes-windows-filesystem-ops).
if (-not $SkipScheduler) {
    Write-Host ""
    Write-Host "Registering daily 09:00 update check (Windows Task Scheduler)..."

    # The /TR argument is a single-quoted PowerShell-invoked bash command. We
    # use a .cmd wrapper to keep the quoting sane. The wrapper lives under
    # $HermesHome\bin so it lives in the same place as the hermes binary
    # (per skill cross-platform-bash-scripting P15: bin/ for invoked binaries).
    $binDir = Join-Path $HermesHome "bin"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null

    $updateCmd = Join-Path $binDir "hermes-dist-update.cmd"
    @"
@echo off
setlocal
cd /d "$DIST_DIR"
git pull --ff-only >nul 2>&1
rem v0.4.0: also check GitHub releases for newer tagged versions
rem and toast the user (no auto-apply)
where curl >nul 2>&1
if %ERRORLEVEL%==0 (
    rem Get the latest tag from GitHub (no auth needed for public releases)
    for /f "delims=" %%t in ('curl -fsSL "https://api.github.com/repos/Somewhatmilk/hermes-dist/releases/latest" 2^>nul ^| findstr /B "  \"tag_name\""') do (
        set "LATEST_TAG=%%t"
    )
    rem Local pinned version lives at "%USERPROFILE%\.hermes\profiles\*.hermes-dist-version"
    set "LOCAL_TAG="
    for /f "delims=" %%f in ('dir /b "%USERPROFILE%\.hermes\profiles\*.hermes-dist-version" 2^>nul') do (
        set "LOCAL_TAG=%%LOCAL_TAG! %%f"
    )
    rem Extract tag_name= "v0.X.Y" via simple parse
    echo %LATEST_TAG% | findstr /C:"\"tag_name\"" >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=2 delims=:, " %%v in ('echo %LATEST_TAG% ^| findstr /C:"\"tag_name\""') do (
            set "GTAG=%%~v"
        )
        rem Strip quotes if any
        set "GTAG=%GTAG:"=%"
        echo Latest operator version: %GTAG%
        echo Your pinned version:    !LOCAL_TAG!
        if not "!LOCAL_TAG!"=="%GTAG%" (
            powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('hermes-dist update available: !GTAG! Run `hermes update-dist` to review and apply.','Hermes Dist','OK','Information')" 2>nul
        )
    )
)
endlocal
"@ | Set-Content -Path $updateCmd -Encoding ASCII

    # Unregister any existing task with the same name (re-install case).
    $existingUpdate = & schtasks /Query /TN $UpdateTaskName 2>$null
    if ($LASTEXITCODE -eq 0) {
        & schtasks /Delete /TN $UpdateTaskName /F | Out-Null
    }

    # /SC DAILY /ST 09:00 — runs at 09:00 every day as the current user.
    # /RL LIMITED — runs with least privilege (no admin token required at run-time).
    # /F — overwrite if exists (belt + braces; we just deleted it).
    & schtasks /Create `
        /TN $UpdateTaskName `
        /TR "`"$updateCmd`"" `
        /SC DAILY /ST 09:00 `
        /RL LIMITED `
        /F
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Registered task: $UpdateTaskName (daily 09:00)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Failed to register $UpdateTaskName (re-run elevated: schtasks /Create ...)" -ForegroundColor Yellow
    }
}

# ─── 10. Register Windows Task Scheduler: 60s heartbeat ───────────────────
if (-not $SkipHeartbeat) {
    Write-Host ""
    Write-Host "Registering 60s heartbeat (Windows Task Scheduler)..."

    $binDir = Join-Path $HermesHome "bin"
    $heartbeatCmd = Join-Path $binDir "hermes-dist-heartbeat.cmd"
    @"
@echo off
setlocal
"$HermesBin" heartbeat --relay "$RelayUrl"
endlocal
"@ | Set-Content -Path $heartbeatCmd -Encoding ASCII

    $existingHeartbeat = & schtasks /Query /TN $HeartbeatTaskName 2>$null
    if ($LASTEXITCODE -eq 0) {
        & schtasks /Delete /TN $HeartbeatTaskName /F | Out-Null
    }

    # /SC MINUTE /MO 1 — every 1 minute. The task restarts itself by virtue
    # of the /RI (restart interval) flag below: if the heartbeat exits 0,
    # the next scheduled run still happens 1 minute later; if it exits
    # non-zero, /RI 1 restarts it after 1 minute.
    & schtasks /Create `
        /TN $HeartbeatTaskName `
        /TR "`"$heartbeatCmd`"" `
        /SC MINUTE /MO 1 `
        /RI 1 `
        /RL LIMITED `
        /F
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Registered task: $HeartbeatTaskName (every 60s)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Failed to register $HeartbeatTaskName (re-run elevated: schtasks /Create ...)" -ForegroundColor Yellow
    }
}

# ─── 11. Final summary ────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Installation Complete (Windows) ===" -ForegroundColor Cyan
Write-Host "  HERMES_HOME:   $HermesHome"
Write-Host "  WORKING_DIR:   $WorkingDir"
Write-Host "  Dist bundle:   $DIST_DIR"
Write-Host "  Relay URL:     $RelayUrl"
Write-Host "  Scheduler:     Task Scheduler task '$UpdateTaskName' (daily 09:00)"
Write-Host "  Heartbeat:     Task Scheduler task '$HeartbeatTaskName' (every 60s)"
Write-Host ""
Write-Host "Launch with: hermes" -ForegroundColor Yellow
Write-Host "Tear down with: .\install-windows.ps1 -Unregister" -ForegroundColor DarkGray