# Hermes Desktop — Fresh-install and dual-install detection (2026-07-02)

## Class of failure

"Fresh-install Hermes Desktop, keep Hermes Agent intact" sounds
simple, but a Hermes Desktop install on Windows is a **5-layer** thing,
not a 1-layer thing. If you only wipe one layer, the next launch will
load stale state from another, the user will see "duplicate slash
command" or other ghost issues, and you'll spend an hour chasing
upstream-source bugs that aren't there.

The same pattern applies to every Hermes sub-app: the bundled source
under `apps/<name>/`, the built artifacts under `apps/<name>/release/`,
the per-profile state under `~/.hermes/<name>/`, the Electron userData
under `%APPDATA%` (Roaming + Local), and any OS-level install under
`%LOCALAPPDATA%\Programs\<name>\`.

## The 5 layers (full Desktop wipe order)

```bash
# Layer 1 — Process tree (kill from leaves up to root)
hermes desktop --stop                # may not exist; fall back to PIDs
powershell -Command "Get-NetTCPConnection -LocalPort 9119 -State Listen |
  Select-Object OwningProcess"        # find actual listener PID
taskkill /F /PID <pid>                # kill listener
# Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match
#   'AppData\\Local\\Programs\\hermes-desktop' } |
#   ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

```bash
# Layer 2 — Source artifacts (the bundle being shipped)
rm -rf apps/desktop/dist             # vite + tsc output (~35MB)
rm -rf apps/desktop/release          # electron-builder --dir output
rm -rf apps/desktop/.vite apps/desktop/node_modules/.vite
rm    apps/desktop/tsconfig.tsbuildinfo
# If user said "wipe source too": git checkout -- apps/desktop/
# If user said "keep source, rebuild fresh": skip git checkout
```

```bash
# Layer 3 — Per-profile state (Hermes CLI's bookkeeping)
rm -rf ~/.hermes/profiles/<name>/desktop.json
rm -rf ~/.hermes/profiles/<name>/desktop/
rm    ~/.hermes/logs/desktop.log     # any log files matching "desktop*"
```

```bash
# Layer 4 — Electron userData + updater (CRITICAL — easy to miss)
# These are inside Windows AppData, NOT under ~/.hermes
rm -rf "$APPDATA/Hermes"            # Roaming\Hermes (Electron default)
rm -rf "$APPDATA/hermes-desktop"    # Roaming\hermes-desktop
rm -rf "$LOCALAPPDATA/hermes-desktop-updater"
rm -rf "$LOCALAPPDATA/Temp/hermes-asar"
# Cache files may be locked briefly by closing processes; retry loop.
```

```bash
# Layer 5 — OS-level installed app + shortcut rewiring
rm -rf "$LOCALAPPDATA/Programs/hermes-desktop"
# Rewrite shortcuts (Start Menu + Desktop) to point at the fixed
# release exe:
powershell -Command "
  $ws = New-Object -ComObject WScript.Shell
  $lnk = '$env:USERPROFILE\Desktop\Hermes One.lnk'
  if (Test-Path $lnk) {
    $s = $ws.CreateShortcut($lnk)
    $s.TargetPath = 'C:\Users\somew\.hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe'
    $s.WorkingDirectory = 'C:\Users\somew\.hermes\hermes-agent\apps\desktop\release\win-unpacked'
    $s.Save()
  }
"
```

## Verification (run BEFORE claiming done)

```bash
# No old app processes alive
powershell -Command "Get-CimInstance Win32_Process |
  Where-Object { \$_.CommandLine -match 'AppData\\\\Local\\\\Programs\\\\hermes-desktop' }"
# Should print: nothing

# No old dirs left
powershell -Command "Test-Path '$env:LOCALAPPDATA\Programs\hermes-desktop';
                    Test-Path '$env:APPDATA\hermes-desktop'"
# Both should be False

# Only the fixed release is running
powershell -Command "Get-Process -Name Hermes -ErrorAction SilentlyContinue |
  Select-Object Id,@{n='Path';e={\$_.MainModule.FileName}} |
  Format-Table -AutoSize"
# All Hermes.exe rows should show the release path.

# Backend listener + healthz
netstat -an | grep 9119             # LISTENING
curl -s http://127.0.0.1:9119/healthz   # HTTP 200
```

## The duplicate-install diagnostic (5 seconds)

If you suspect TWO installs of Hermes Desktop are running:

```bash
powershell -Command "Get-Process -Name Hermes -ErrorAction SilentlyContinue |
  Where-Object { \$_.MainModule.FileName -like '*hermes-desktop*' -or
                 \$_.MainModule.FileName -like '*Hermes.exe' } |
  Select-Object Id,@{n='Path';e={\$_.MainModule.FileName}} |
  Format-Table -AutoSize"
```

Look for two different paths:

- `C:\Users\somew\.hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe` (the freshly-built release)
- `C:\Users\somew\AppData\Local\Programs\hermes-desktop\hermes-agent.exe` (a previous install)

You can ALSO check `--app-path=...` in the renderer process command
line. Electron always sets it. That tells you which `app.asar` each
window is actually loading — perfect for "is this window using the
fixed bundle or the old one?"

```bash
powershell -Command "Get-CimInstance Win32_Process |
  Where-Object { \$_.CommandLine -match '--type=renderer.*hermes-desktop' } |
  Select-Object ProcessId,@{n='AppPath';e={
    if (\$_.CommandLine -match '--app-path=\"([^\"]+)\"') { \$Matches[1] } else { '' }
  }} | Format-Table -AutoSize"
```

## The bash/MSYS launch-exit-code quirk

`hermes serve --skip-build --port 9119` and `hermes desktop --skip-build`
are launcher scripts that spawn detached children. On Git Bash / MSYS
Windows, the launcher may return exit code 1 after the child has
launched successfully. The output (`HERMES_DASHBOARD_READY port=9119`,
`→ Launching packaged Hermes Desktop: ...`) is the actual success
signal — exit code is unreliable.

Verify by:

1. `netstat -an | grep 9119` — backend listener is bound
2. `curl http://127.0.0.1:9119/healthz` — backend HTTP 200
3. `Get-Process Hermes` — Electron main is alive

Don't waste time chasing "exit code 1" from these launchers — the
launcher exited, the child is fine.

## Why this isn't documented elsewhere

- `hermes-agent` skill mentions `hermes serve` exists but doesn't say
  "the desktop requires it running first" (covered by
  `desktop-backend-required-2026-07-02.md`).
- The desktop install is split across `apps/desktop/` (source),
  `%APPDATA%` (Electron cache), `%LOCALAPPDATA%\Programs\` (installed
  app) — no single skill covers all 5 layers.
- The duplicate-install detection relies on comparing exe paths AND
  Electron `--app-path` renderer args; this isn't in any tutorial.

## Three rules to remember

- **"Fresh install" of a Hermes sub-app = 5 layers, not 1.** If the
  user says "fresh install" without naming layers, ask which they mean
  (source, build artifacts, per-profile state, Electron userData,
  OS install) — but default to wiping all 5 unless they pin one.
- **Two installs of Hermes Desktop can coexist silently.** Always check
  MainModule.FileName and renderer --app-path args before assuming
  "the running app is the one I built."
- **MSYS launch exit codes are unreliable for Hermes launcher scripts.**
  Verify by listener + healthz + process path, not by exit code.