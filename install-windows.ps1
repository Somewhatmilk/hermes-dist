# install-windows.ps1
# Hermes Dist installer for Windows 10/11.
# PowerShell 5.1+ (the version that ships with Windows 10) and PowerShell 7+ both supported.
#
# Usage (in an elevated PowerShell — not strictly required, but recommended
# for the scheduled-task step):
#   .\install-windows.ps1 -RelayUrl "https://relay.your-domain" -DistRepo "https://github.com/Somewhatmilk/hermes-dist.git"
#
# Or with defaults (registers with localhost relay for testing):
#   .\install-windows.ps1
#
# Idempotent. Re-run safely.
#
# What this does:
#   1. Verify Python 3.11+ and Git are present
#   2. Install Hermes Agent if not already installed
#   3. Clone or update the hermes-dist repo
#   4. Run .onboard.sh (the cross-OS first-launch script) via Git Bash
#   5. Register heartbeat scheduled task (push-update channel)
#   6. Register daily git pull scheduled task
#   7. Optionally start tinysearch Docker container
#   8. Print summary

[CmdletBinding()]
param(
    [string]$RelayUrl = "https://relay.local",
    [string]$DistRepo = "https://github.com/Somewhatmilk/hermes-dist.git",
    [string]$HermesHome = "$env:USERPROFILE\.hermes",
    [switch]$Reinstall,
    [switch]$NoHeartbeat,
    [switch]$NoScheduledTasks
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ── Logging ────────────────────────────────────────────────────────────────
function Write-Step    { param($m) Write-Host "  $m" -ForegroundColor Green }
function Write-Warn    { param($m) Write-Host "  $m" -ForegroundColor Yellow }
function Write-Err     { param($m) Write-Host "  $m" -ForegroundColor Red }
function Write-Info    { param($m) Write-Host "  $m" -ForegroundColor Cyan }

# ── 0. Banner ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Hermes Dist Installer — Windows ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python check (cross-OS: try python3, then python) ───────────────────
$py = $null
foreach ($candidate in @("python3", "python", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        $ver = & $candidate -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($ver -match '^3\.(1[1-9]|[2-9]\d|1\d{2,})$') {
            $py = $candidate
            break
        }
    }
}
if (-not $py) {
    Write-Err "Python 3.11+ not found. Install from https://www.python.org/downloads/"
    Write-Err "Make sure 'Add Python to PATH' is checked during install."
    exit 1
}
Write-Step "Python: $(& $py --version)"

# ── 2. Git check ──────────────────────────────────────────────────────────
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Err "Git not found. Install from https://git-scm.com/download/win"
    exit 1
}
Write-Step "Git: $(git --version)"

# ── 3. Find Git Bash ──────────────────────────────────────────────────────
$bash = $null
$bashCandidates = @(
    "C:\Program Files\Git\bin\bash.exe",
    "C:\Program Files (x86)\Git\bin\bash.exe",
    "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe",
    "$env:ProgramFiles\Git\bin\bash.exe"
)
foreach ($c in $bashCandidates) {
    if (Test-Path $c) { $bash = $c; break }
}
# Fallback: rely on PATH
if (-not $bash) {
    $bashCmd = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($bashCmd) { $bash = $bashCmd.Source }
}
if (-not $bash) {
    Write-Err "bash.exe not found. Install Git for Windows from https://git-scm.com/download/win"
    exit 1
}
Write-Step "Git Bash: $bash"

# ── 4. Install Hermes if missing ──────────────────────────────────────────
$hermesBin = Get-Command hermes -ErrorAction SilentlyContinue
if (-not $hermesBin -or $Reinstall) {
    Write-Host ""
    Write-Host "Installing Hermes Agent via official installer..."
    try {
        irm https://hermes-agent.nousresearch.com/install.ps1 | Invoke-Expression
    } catch {
        Write-Err "Failed to install Hermes Agent: $_"
        Write-Err "Install manually from https://hermes-agent.nousresearch.com/install"
        exit 1
    }
    $hermesBin = Get-Command hermes -ErrorAction SilentlyContinue
    if (-not $hermesBin) {
        Write-Err "Hermes not found in PATH after install. Open a new PowerShell and retry."
        exit 1
    }
} else {
    Write-Step "Hermes: $(hermes version 2>$null | Select-Object -First 1)"
}

# ── 5. Clone or update the dist repo ──────────────────────────────────────
$DIST_DIR = Join-Path $HermesHome ".." "hermes-dist" | Resolve-Path -ErrorAction SilentlyContinue
if (-not $DIST_DIR) { $DIST_DIR = "$env:USERPROFILE\hermes-dist" }
$DIST_DIR = [System.IO.Path]::GetFullPath((Join-Path $env:USERPROFILE "hermes-dist"))

if (Test-Path "$DIST_DIR\.git") {
    Write-Step "Using existing $DIST_DIR"
    if ($Reinstall) {
        Push-Location $DIST_DIR
        try { git fetch --depth=1 origin master 2>&1 | Select-Object -First 5 } catch {}
        Pop-Location
    }
} else {
    Write-Host "Cloning $DistRepo to $DIST_DIR..."
    git clone --depth=1 $DistRepo $DIST_DIR
}

if (-not (Test-Path "$DIST_DIR\.onboard.sh")) {
    Write-Err ".onboard.sh not found in $DIST_DIR"
    exit 1
}

# ── 6. Run .onboard.sh via Git Bash ───────────────────────────────────────
$env:HERMES_HOME = $HermesHome
$env:HERMES_DIST_REPO = $DistRepo
$env:HERMES_RELAY_URL = $RelayUrl

Write-Host ""
Write-Host "Running first-launch onboarding (.onboard.sh)..."
& $bash "$DIST_DIR\.onboard.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Err ".onboard.sh failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

# ── 7. Register heartbeat scheduled task ──────────────────────────────────
if (-not $NoHeartbeat) {
    $hbScript = "$HermesHome\.hermes-dist-heartbeat.sh"
    $hbSrc = "$DIST_DIR\install-common\heartbeat.sh"
    if (Test-Path $hbSrc) {
        Copy-Item -Force $hbSrc $hbScript
        Write-Step "Heartbeat script installed at $hbScript"

        $taskName = "HermesDistHeartbeat"
        $action = New-ScheduledTaskAction `
            -Execute $bash `
            -Argument "-c `"$hbScript`"" `
            -WorkingDirectory $HermesHome
        # Heartbeat every 5 minutes; the script self-throttles to 30s
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Minutes 5) `
            -RepetitionDuration (New-TimeSpan -Days 3650)
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

        try {
            Register-ScheduledTask `
                -TaskName $taskName `
                -Action $action `
                -Trigger $trigger `
                -Principal $principal `
                -Settings $settings `
                -Force `
                -ErrorAction Stop | Out-Null
            Write-Step "Heartbeat scheduled task registered (every 5 min; script self-throttles to 30s)"
        } catch {
            Write-Warn "Failed to register heartbeat task: $_"
        }
    } else {
        Write-Warn "heartbeat.sh not found in $DIST_DIR\install-common\ - push updates disabled"
    }
}

# ── 8. Register daily git pull (catches operator changes between heartbeats) ──
if (-not $NoScheduledTasks) {
    $taskName = "HermesDistDailyUpdate"
    $action = New-ScheduledTaskAction `
            -Execute $bash `
            -Argument "-c `"cd '$DIST_DIR'; git pull --ff-only 2>&1 | head -20`""
    $trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited

    try {
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Principal $principal `
            -Force `
            -ErrorAction Stop | Out-Null
        Write-Step "Daily update check registered at 09:00"
    } catch {
        Write-Warn "Failed to register daily update task: $_"
    }
}

# ── 9. Optional tinysearch container ─────────────────────────────────────
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    Write-Host ""
    $existing = & docker ps -a --filter "name=hermes-tinysearch" --format "{{.Names}}" 2>$null
    if ($existing -eq "hermes-tinysearch") {
        & docker start hermes-tinysearch 2>$null | Out-Null
        Write-Step "tinysearch container started"
    } else {
        & docker pull hermes/tinysearch:latest 2>$null | Out-Null
        & docker run -d --name hermes-tinysearch -p 127.0.0.1:8000:8000 --restart unless-stopped hermes/tinysearch:latest 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Step "tinysearch running at http://127.0.0.1:8000"
        } else {
            Write-Warn "tinysearch failed to start (non-fatal). Web scraping falls back to direct HTTP."
        }
    }
} else {
    Write-Warn "Docker not found. Web scraping will fall back to direct HTTP (Camofox still works for browser)."
}

# ── 10. Summary ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host "  Hermes home:    $HermesHome"
Write-Host "  Dist bundle:    $DIST_DIR"
Write-Host "  Relay URL:      $RelayUrl"
Write-Host "  Heartbeat:      every 30s (operator push channel)"
Write-Host "  Daily update:   09:00 (git pull fallback)"
Write-Host ""
Write-Host "Launch with: hermes" -ForegroundColor Yellow
Write-Host "Or run the desktop app from the Start menu." -ForegroundColor Yellow
