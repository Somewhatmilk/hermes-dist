# install-windows.ps1
# Hermes Dist PoC — Windows installer.
# Single-OS PoC. Mac/Linux installers come after Phase 1 verification.
#
# Usage (in an elevated PowerShell):
#   .\install-windows.ps1 -RelayUrl "https://relay.your-domain" -DistRepo "https://github.com/you/hermes-dist"
#
# Or with defaults (registers with localhost relay for testing):
#   .\install-windows.ps1

[CmdletBinding()]
param(
    [string]$RelayUrl = "https://relay.local",
    [string]$DistRepo = "",
    [string]$HermesHome = "$env:USERPROFILE\.hermes"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Hermes Dist PoC — Windows Installer ===" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Verify prerequisites ───────────────────────────────────────────────
$prereqs = @(
    @{ name = "Python 3.11+"; check = { & python --version 2>&1 | Select-String "Python 3\.(1[1-9]|[2-9]\d)" } },
    @{ name = "Git"; check = { & git --version 2>&1 } },
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
            Write-Host "    Install it from https://www.python.org/downloads/ and https://git-scm.com/download/win" -ForegroundColor Yellow
            exit 1
        }
    }
}

# ─── 2. Install Hermes Agent if not present ────────────────────────────────
if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Installing Hermes Agent via official installer..."
    $installScript = irm "https://hermes-agent.nousresearch.com/install.ps1"
    Invoke-Expression $installScript
} else {
    Write-Host "  ✓ Hermes Agent already installed: $(hermes version)" -ForegroundColor Green
}

# ─── 3. Clone the hermes-dist repo (or use local path) ─────────────────────
$DIST_DIR = "$HermesHome\..\hermes-dist"
if (Test-Path $DIST_DIR) {
    Write-Host "  ✓ Using existing $DIST_DIR" -ForegroundColor Green
} else {
    if ($DistRepo) {
        Write-Host "Cloning $DistRepo to $DIST_DIR..."
        & git clone $DistRepo $DIST_DIR
    } else {
        Write-Host "  ⚠ No -DistRepo specified and no local hermes-dist found." -ForegroundColor Yellow
        Write-Host "    Either specify -DistRepo or copy the hermes-dist folder to $DIST_DIR manually." -ForegroundColor Yellow
        exit 1
    }
}

# ─── 4. Run .onboard.sh via Git Bash ───────────────────────────────────────
$OnboardScript = "$DIST_DIR\.onboard.sh"
if (-not (Test-Path $OnboardScript)) {
    Write-Host "  ✗ .onboard.sh not found in $DIST_DIR" -ForegroundColor Red
    exit 1
}

# Find bash.exe (Git Bash on Windows)
$bash = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
if (-not $bash) {
    $bashCandidates = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files (x86)\Git\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
    )
    foreach ($c in $bashCandidates) {
        if (Test-Path $c) { $bash = $c; break }
    }
}
if (-not $bash) {
    Write-Host "  ✗ bash.exe not found. Install Git for Windows." -ForegroundColor Red
    exit 1
}

$env:HERMES_HOME = $HermesHome
$env:HERMES_DIST_REPO = $DistRepo
$env:HERMES_RELAY_URL = $RelayUrl

Write-Host ""
Write-Host "Running .onboard.sh..."
& $bash $OnboardScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ .onboard.sh failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# ─── 5. Start tinysearch Docker container if Docker is available ───────────
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "Starting tinysearch Docker container..."
    $existing = & docker ps -a --filter "name=hermes-tinysearch" --format "{{.Names}}" 2>$null
    if ($existing -eq "hermes-tinysearch") {
        & docker start hermes-tinysearch 2>$null
    } else {
        # Pull or use local image
        & docker pull hermes/tinysearch:latest 2>$null
        & docker run -d --name hermes-tinysearch -p 127.0.0.1:8000:8000 --restart unless-stopped hermes/tinysearch:latest
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ tinysearch running at http://127.0.0.1:8000" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ tinysearch failed to start. Web scraping will fall back to direct HTTP." -ForegroundColor Yellow
    }
}

# ─── 6. Register Windows Task Scheduler for daily update check ────────────
Write-Host ""
Write-Host "Registering daily update check (Windows Task Scheduler)..."
$taskName = "HermesDistUpdateCheck"
$action = New-ScheduledTaskAction -Execute $bash -Argument "-c `"cd '$DIST_DIR' && git pull --ff-only 2>&1 | head -20`""
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
    Write-Host "  ✓ Daily update check registered" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Failed to register scheduled task: $_" -ForegroundColor Yellow
}

# ─── 7. Final summary ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host "  Hermes home:    $HermesHome"
Write-Host "  Dist bundle:    $DIST_DIR"
Write-Host "  Relay URL:      $RelayUrl"
Write-Host ""
Write-Host "Launch with: hermes" -ForegroundColor Yellow
Write-Host "Or run the desktop app from the Start menu." -ForegroundColor Yellow
