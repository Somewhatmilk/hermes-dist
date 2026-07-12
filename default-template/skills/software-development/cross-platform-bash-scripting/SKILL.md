---
name: cross-platform-bash-scripting
description: "Write bash scripts that run on Windows MSYS/Cygwin, Mac, and Linux without forking — OSTYPE-aware path resolution, extension dispatch, env-var-with-default-fallback, the cmd //c Windows-only trap, the dispatch patterns for cron / launchd / systemd / Task Scheduler, the CPython→bash subprocess path bridge, and the verifier-side complement for piping bash scripts through `bash -n` from CPython on Windows. Use when authoring any shell script that lives under $HERMES_HOME/scripts/, $OCD_DIR/sync-*.sh, install/install.sh, watcher scripts, or any cron-attached bash file. Also use when porting an existing bash script from one OS to another, or when writing an ad-hoc verifier (Python or otherwise) that drives bash from a subprocess."
version: 1.2.0
author: Hermes Agent (default profile)
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [bash, shell, cross-platform, ostype, msys, darwin, cron, launchd, systemd, path-bridge, to-native-path, cpython-subprocess, verifier, stdin-pipe]
    category: software-development
    related_skills: [session, hermes-skill-refactor, hermes-skill-authoring, hermes-misbehavior-diagnosis, windows-wsl2-hermes, hermes-windows-filesystem-ops]
    config: [] 
---

# cross-platform-bash-scripting

> **Use this skill when:** you're writing a bash script that needs to run
> on Windows MSYS/Cygwin, macOS, AND Linux without forking into 3 files.
> Common scenarios: `$HERMES_HOME/scripts/*.sh`, OCD sync/backup scripts,
> install/install.sh, install/recover.sh, watcher scripts, scheduled-job
> wrappers, environment-aware helpers.
>
> **Do NOT use this skill when:** the script is OS-specific by design (a
> Windows-only PowerShell wrapper, a mac-only launchctl helper). For those,
> just write the OS-specific version.

## The single-source-of-truth pattern

Every cross-platform script has the same 3 sections, in this order:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. SHEBANG + set -euo pipefail                                  │
├─────────────────────────────────────────────────────────────────┤
│ 2. PATH RESOLUTION via OSTYPE case                              │
│    (compute _USER_DIR, _HERMES_EXE_SUBDIR, etc. as locals)     │
├─────────────────────────────────────────────────────────────────┤
│ 3. ENV-VAR OVERRIDE + default fallback                          │
│    : "${HERMES_HOME:=$_USER_DIR/.hermes}"                       │
│    # → user can override via env, otherwise auto-detected        │
├─────────────────────────────────────────────────────────────────┤
│ 4. COMMAND DISPATCH via OSTYPE case                             │
│    (which binary, which extension, which scheduler)             │
├─────────────────────────────────────────────────────────────────┤
│ 5. MAIN WORK — same code path for all 3 OSes                    │
└─────────────────────────────────────────────────────────────────┘
```

Sections 1-4 are copy-paste across scripts. Section 5 is the actual logic
and is OS-agnostic. **The mistake to avoid:** writing section 5 with
hardcoded `/c/Users/somew/...` paths and discovering at runtime that the
Mac user's `$HOME/Downloads/One-Cut-Deeper` path was assumed Windows.

## Section 2 — Path resolution pattern (canonical)

This is the exact pattern that works. Copy it.

```bash
# === Compute OS-specific defaults ===
case "${OSTYPE:-}" in
    msys*|cygwin*)
        # Windows MSYS bash: $HOME is the Windows user profile (e.g. C:\Users\name).
        # MSYS gives us a /c/Users/name style path that all tools understand.
        _USER_DIR="$HOME"
        _HERMES_EXE_SUBDIR="hermes-agent/venv/Scripts"
        _HERMES_EXE_NAME="hermes.exe"
        _BIN_EXT="cmd //c"          # Windows uses cmd //c for .bat/.exe
        _SCHEDULER="schtasks"
        _SCHEDULER_CMD='/create /tn "X" /tr "Y" /sc daily /st 03:00'
        ;;
    darwin*|linux*)
        _USER_DIR="$HOME"
        _HERMES_EXE_SUBDIR="hermes-agent/venv/bin"
        _HERMES_EXE_NAME="hermes"
        _BIN_EXT=""
        case "${OSTYPE}" in
            darwin*) _SCHEDULER="launchctl"; _SCHEDULER_CMD="load -w" ;;
            linux*)  _SCHEDULER="systemctl"; _SCHEDULER_CMD="enable --now" ;;
        esac
        ;;
    *)
        echo "ERROR: unsupported OS '$OSTYPE'. Edit this script to add it." >&2
        exit 1
        ;;
esac
```

**Then derive everything else from the local variables** instead of
hardcoding anything:

```bash
: "${OCD_DIR:=$_USER_DIR/Downloads/One-Cut-Deeper}"   # env-override + default
: "${HERMES_HOME:=$_USER_DIR/.hermes}"
MNEMOSYNE_HERMES="$HERMES_HOME/$_HERMES_EXE_SUBDIR/$_HERMES_EXE_NAME"
PLAYWRIGHT_SRC="$_USER_DIR/Desktop/Hermes/playwright-research"
```

**The `_USER_DIR` indirection is load-bearing.** Every path becomes a
formula off `_USER_DIR` — never a literal `/c/Users/somew/...`. Move the
formula around and the whole script moves with it.

## Section 3 — Env-var-with-default-fallback (canonical)

This is the `: "${VAR:=default}"` pattern. The colon is required (otherwise
unset vars cause `[ -z ]` errors under `set -u`):

```bash
: "${OCD_DIR:=$_USER_DIR/Downloads/One-Cut-Deeper}"
: "${HERMES_HOME:=$_USER_DIR/.hermes}"
: "${HF_REPO_GEMMA:=unsloth/gemma-4-26b-it-q4_k_xl}"
```

**Properties:**
- If the user already exported `OCD_DIR=...` before running, the override wins.
- If they didn't, the auto-detected default is used.
- `set -u` doesn't fire because the `:=` guarantees the var is set.
- The colon-prefix is required; `: "${VAR:=default}"` not `[ -z "$VAR" ] && VAR=default`.

**Note about Tilde expansion:** `${HOME}` works, `~` in a default value
does not get expanded. Always use `$_USER_DIR` (already $HOME) in the
defaults, not `~`.

## Section 4 — Command dispatch (the 5 patterns you actually need)

### 4a. Windows-only `cmd //c` is a TRAP

```bash
# BAD — breaks on Mac and Linux:
cmd //c "rmdir /s /q profiles"

# GOOD — gated to MSYS only, fallback for the rest:
case "${OSTYPE:-}" in
    msys*|cygwin*) cmd //c "rmdir /s /q profiles" 2>/dev/null || true ;;
    *)             rm -rf profiles/ 2>/dev/null || true ;;
esac
```

`cmd //c` is MSYS-specific and the `//c` is necessary to prevent MSYS
path translation. Without the gating, Mac/Linux fail with
`cmd: command not found`.

### 4b. Python venv bin path differs by OS

| OS | Path |
|---|---|
| Windows MSYS | `venv/Scripts/python.exe` |
| Mac/Linux | `venv/bin/python` |

Set the variables once via the OSTYPE case (§2), then reference everywhere:
```bash
"$HERMES_HOME/$_HERMES_EXE_SUBDIR/python" script.py    # never literalize
```

### 4c. Binary executable suffix

| OS | Hermes binary |
|---|---|
| Windows | `hermes.exe` |
| Mac/Linux | `hermes` |

Same pattern — `_HERMES_EXE_NAME` local from the OSTYPE case.

### 4d. Cron dispatch (the right way to register on each OS)

This is **the** recipe that install/install.sh uses (validated 2026-07-03):

```bash
case $OS in
    windows)
        # PS1 helpers register the Task Scheduler entry
        powershell -ExecutionPolicy Bypass -File "$HERMES_HOME/scripts/hermes-automation-register.ps1"
        ;;
    mac)
        # Per-user LaunchAgent — ~/Library/LaunchAgents/com.<label>.plist
        # Use `launchctl load -w` to register
        local launch_agents_dir="$HOME/Library/LaunchAgents"
        mkdir -p "$launch_agents_dir"
        cat > "$launch_agents_dir/com.user.hermes-state-backup.plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.user.hermes-state-backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HERMES_HOME/$_HERMES_EXE_SUBDIR/$_HERMES_EXE_NAME</string>
        <string>state-backup</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>$HERMES_HOME/logs/state-backup.log</string>
    <key>StandardErrorPath</key><string>$HERMES_HOME/logs/state-backup.err</string>
</dict>
</plist>
PLIST_EOF
        launchctl load -w "$launch_agents_dir/com.user.hermes-state-backup.plist"
        ;;
    linux)
        # systemd user timer — ~/.config/systemd/user/
        mkdir -p "$HOME/.config/systemd/user"
        cat > "$HOME/.config/systemd/user/hermes-state-backup.service" <<SVC_EOF
[Unit]
Description=Hermes state backup

[Service]
Type=oneshot
ExecStart=$HERMES_HOME/$_HERMES_EXE_SUBDIR/$_HERMES_EXE_NAME state-backup
SVC_EOF
        cat > "$HOME/.config/systemd/user/hermes-state-backup.timer" <<TMR_EOF
[Unit]
Description=Daily hermes state backup at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
TMR_EOF
        systemctl --user enable --now hermes-state-backup.timer
        ;;
esac
```

**Critical differences:**
- Mac uses `launchctl load -w`; `launchctl unload` first if re-registering.
- Linux uses `systemctl --user` (not system — user-scoped, no sudo).
- Windows uses Task Scheduler via `.ps1` helper (UAC + elevation can't
  be scripted unattended).

### 4e. Asset download + extract by extension

When downloading platform-specific binaries from a release page, dispatch
on the filename extension. Canonical pattern (install_desktop in install.sh):

```bash
case "$asset_name" in
    *.dmg)    # Mac — don't auto-run hdiutil (needs password); just copy
              cp "$tmpdir/$asset_name" "$HERMES_HOME/desktop/"
              ;;
    *.exe)    # Windows — don't auto-elevate UAC; copy for manual run
              cp "$tmpdir/$asset_name" "$HERMES_HOME/desktop/"
              ;;
    *.AppImage)
              chmod +x "$tmpdir/$asset_name"
              mv "$tmpdir/$asset_name" "$HERMES_HOME/desktop/"
              ;;
    *.deb)
              sudo dpkg -i "$tmpdir/$asset_name"
              ;;
    *.zip|*.tar.gz)
              tar -xzf "$tmpdir/$asset_name" -C "$tmpdir"
              cp -r "$tmpdir"/*/Hermes.app "$HERMES_HOME/desktop/"
              ;;
esac
```

## The 14 most-common pitfalls (8 carried over + 6 new for 2026-07-03)

### P1. Hardcoded `/c/Users/somew/` paths
**Symptom:** script works on your machine, fails on the user's Mac.
**Fix:** every literal `/c/Users/somew/...` becomes `$_USER_DIR/...`
where `_USER_DIR` is derived from `OSTYPE`.

### P2. `cmd //c` outside MSYS
**Symptom:** `cmd: command not found` on Mac/Linux.
**Fix:** gate the `cmd //c` line to `msys*|cygwin*)` only, with a `rm -rf`
fallback for everything else.

### P3. `venv/Scripts/python` on Mac/Linux
**Symptom:** `python: command not found` despite `pip install` succeeding.
**Fix:** `_HERMES_EXE_SUBDIR="hermes-agent/venv/bin"` for Mac/Linux,
`Scripts` for Windows. Single local var from the OSTYPE case.

### P4. `hermes.exe` literal on Mac/Linux
**Symptom:** `cannot find hermes.exe`. Or worse, the script runs the
script with the literal name `hermes.exe` as a command and "succeeds" silently.
**Fix:** `_HERMES_EXE_NAME="hermes"` for Mac/Linux, `hermes.exe` for Windows.

### P5. `${HOME}` vs `~` in defaults
**Symptom:** default value `~/Downloads` stays literal `~/Downloads`
because tilde isn't expanded in parameter expansion defaults.
**Fix:** use `${HOME}` everywhere, or `$_USER_DIR` (which equals `$HOME`).

### P6. `set -u` + unset env var
**Symptom:** script crashes with `VAR: unbound variable` when run with
`VAR` unset.
**Fix:** use `: "${VAR:=default}"` not `[ -z "$VAR" ] && VAR=default`. The
`:` makes it a no-op assignment; the `:=` sets and exports; the quotes
guard against whitespace.

### P7. `find` output containing filenames with spaces
**Symptom:** `for f in $(find .)` silently splits on spaces.
**Fix:**
```bash
find . -type f -print0 | while IFS= read -r -d '' f; do
    echo "file: $f"
done
```
The `-print0` + `read -d ''` pair handles any filename. Use this for every `find ... | while read` pattern in sync scripts, register scripts, and watcher scripts. **Without `-print0`, filenames with spaces (e.g. `My Documents`) silently disappear from the processing loop.**
### P8. `cat <<EOF` with `$variable` substitution

**Symptom:** heredoc with `$VAR` in the body interpolates from the shell context, even if the heredoc is meant to be a template.

**Fix:**

- Single-quoted `<<'EOF'` (literal, no interpolation) — use when writing
  a template or a JSON snippet.
- Unquoted `<<EOF` (interpolated) — use when you want shell vars to land
  in the heredoc output (e.g. the launchd plist pattern above, where
  `$HERMES_HOME` MUST be substituted).

Don't mix them up — it's the #1 source of "why is my plist literally
`$HERMES_HOME` instead of `/c/Users/somew/.hermes`" bugs.

### P9. Python scripts under `$HERMES_HOME/scripts/` must use the `_hermes_paths.py` shim

Symptom: `~/.hermes/research/manifest.json` exists and is the source of truth, but your Python watcher writes to `C:\Users\somew\AppData\Local\hermes\research\` (or vice versa). When the user runs `python watch_comfyui.py`, it silently fails to update the canonical manifest, or it overwrites a different one, and the next session reads stale data.

Fix: never hardcode either path. Add at the top of any Python script under `$HERMES_HOME/scripts/`:

```python
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _hermes_paths import get_hermes_home
    HERMES_HOME = get_hermes_home()
except ImportError:
    HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / "AppData" / "Local" / "hermes"))

# then use HERMES_HOME / "research" / "your-file.json" everywhere
MANIFEST_PATH = HERMES_HOME / "research" / "manifest.json"
```

The shim resolves in this order: `$HERMES_HOME` env var → `$LOCALAPPDATA/hermes` (Windows) → `$XDG_DATA_HOME/hermes` (Linux) → `~/.local/share/hermes` (Linux fallback) → `~/.hermes` (Linux legacy). On the user's Windows host, `$HERMES_HOME` is set to `C:/Users/somew/.hermes` (the legacy path), NOT `AppData/Local/hermes`. If your script hardcodes `AppData/Local`, your writes go to the wrong directory.

Also: **mirror the script to `~/.hermes/scripts/`** if the user expects to find it there. The agent runs scripts from `$HERMES_HOME/scripts/` (resolved via the shim), but the user browses/edits `~/.hermes/scripts/`. If you only write to one location, the user gets confused when they can't find the file in their CWD. Pattern: write the file in the canonical location, then `cp` it to `~/.hermes/scripts/` so both work.

The user's call-out 2026-07-03: "where is the watcehr located? why isnt it in cwd scripts folder?" — they were looking for `watch_comfyui.py` in `~/.hermes/scripts/` and couldn't find it because the canonical location is `$HERMES_HOME/scripts/` which resolves elsewhere.

### P10. PowerShell `.ps1` files that shell out to bash need a `Get-BashExe()` helper (NEW 2026-07-03)

**Symptom:** hardcoded `C:\Program Files\Git\bin\bash.exe` in a `.ps1` register/cron script fails on any box where Git was installed to a non-default location (x86, $LOCALAPPDATA, winget, scoop, choco) or where the user uses WSL instead of Git Bash.

**Fix — put this helper at the top of every `.ps1` that runs bash:**

```powershell
function Get-BashExe {
    $candidates = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files (x86)\Git\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
    )
    foreach ($b in $candidates) { if (Test-Path $b) { return $b } }
    $wsl = (Get-Command wsl.exe -ErrorAction SilentlyContinue)
    if ($wsl) { return "wsl.exe" }
    return "bash"   # last resort — hope it's on PATH
}
$bashExe = Get-BashExe
if ($bashExe -eq "bash") {
    Write-Warning "bash.exe not found in standard Git for Windows locations. Falling back to 'bash' on PATH. Scheduled task may fail at run-time if PATH is minimal."
}
```

Then `$bashExe` is your `New-ScheduledTaskAction -Execute $bashExe`. Never reference `bash.exe` literally after that. Pair with `set -euo pipefail` in the bash script so failures surface in the scheduled-task log instead of being silently swallowed. Also pair with `param([string]$HermesHome = $env:HERMES_HOME, [switch]$Unregister, [switch]$UnregisterOnly)` so every register/unregister script has a consistent parameter story. Wire `HERMES_HOME` to `$env:HERMES_HOME` and fall back to `Join-Path $env:USERPROFILE ".hermes"`. This avoids hardcoded `C:\Users\somew\...` in `.ps1` files.

### P11. `lsp/` + `browser_screenshots/` + `cache/` exclusions in profile sync scripts (NEW 2026-07-03, hot)

**Symptom:** `~/.hermes/profiles/*/lsp/node_modules` is 1-2GB of vendored Python stubs (Pyright + Intelephense). `profiles/*/browser_screenshots` and `profiles/*/cache/screenshots/*.png` are 150-185KB debug screenshots from camofox browser sessions. The bash sync's `find -type f | cp` does **not** skip these by default. Result on the user's Windows host as of 2026-07-03: 8,009 files / 135M in profiles/, the sync stalls at the cp step for 12+ minutes.

**Fix — add to the `find` filter in the profile-sync step of `one-cut-deeper-sync.sh` (and any other sync that touches `profiles/`):**

```bash
find "$PROFILES_SRC" -type f \
    -not -name "*.db" \
    -not -name "*.sqlite*" \
    -not -name "*.lock" \
    -not -path "*/lsp/node_modules/*" \
    -not -path "*/browser_screenshots/*" \
    -not -path "*/cache/screenshots/*" \
    | while IFS= read -r -d '' file; do
        rel_path="${file#$PROFILES_SRC/}"
        mkdir -p "$(dirname "profiles/$rel_path")"
        cp "$file" "profiles/$rel_path"
    done
```

Also add to the script's embedded `.gitignore` block:

```gitignore
profiles/*/lsp/node_modules/
profiles/*/browser_screenshots/
profiles/*/cache/screenshots/
```

Verified on 2026-07-03: 12-min sync stall measured live, the fix would cut the profile sync to ~30 seconds by excluding ~2GB of `lsp/node_modules` + ~50MB of screenshots. The cross-platform-bash-scripting skill's own `scripts/sanity-check.sh` should also grow a grep for these patterns.

### P12. Killing a long sync mid-flight → D-storm recovery (NEW 2026-07-03)

**Symptom:** the sync script does `git rm -r profiles/` then the user/kill kills it before the rebuild. Result: `git status` shows ~9000 `D` (deleted) entries in `profiles/`, skill bundling broken, next sync starts from broken state.

**Fix — after killing a mid-sync (or any bash script that does destructive `rm`/`git rm` followed by rebuild):**

```bash
# restore from HEAD, then re-run with a filter that won't stall
git checkout HEAD -- profiles/ skills/ hermes-scripts/
# Verify the tree is recoverable
git -C /c/Users/somew/Downloads/One-Cut-Deeper status --short | wc -l   # should be small again
```

The recipe: the destructive `git rm` is the only place a half-killed sync can leave the repo in a broken state. `git stash` is **worse** here because the staged deletes and the unstaged deletions both need to land together; `git checkout HEAD -- <dir>` is the only safe undo.

**Class lesson:** any sync script that does `git rm -r <dir> && cp <new>` is fragile. The canonical fix is to (a) make the cp part fast (add the P11 exclusions), (b) if you must kill the sync, `git checkout HEAD -- <dir>` is the recovery, not `git stash` and not `git restore`. Add this to your runbook for any future bash `git rm -r` script.

### P13. `HERMES_HOME` on Windows resolves to the legacy path, NOT `AppData/Local` (NEW 2026-07-03)

**Symptom:** you hardcode `$HOME/AppData/Local/hermes` (the modern Windows convention) but the live `$HERMES_HOME` actually points to `$HOME/.hermes` (the legacy MSYS-friendly path). Or vice versa. Writable paths get misread.

**Fix — always resolve via `get_hermes_home` from `_hermes_paths.py` (Python) or these fallbacks in bash, in order:**

1. `$env:HERMES_HOME` (Windows PowerShell) / `$HERMES_HOME` (bash) — explicit override, always wins.
2. On Windows MSYS: `$HOME` is the Windows profile, but the **live hermes install is `$HOME/.hermes`** for legacy/MSYS-friendliness, not `$HOME/AppData/Local/hermes`.
3. On Mac/Linux: `$HOME/.hermes`.

The right cross-platform default is `$_USER_DIR/.hermes` on Mac/Linux AND on Windows MSYS. If the user is running native Windows (not MSYS), they should set `HERMES_HOME` explicitly. Audit any path like `~/AppData/Local/hermes` and replace with `$_USER_DIR/.hermes`.

### P15. `bin/` is for invoked binaries, `scripts/` is for sourced libraries (NEW 2026-07-09)

**Symptom:** User asks "what does bin mean / can it be used for anything else / is it the technical term for scripts" — the agent has to explain. The vocabulary has a Unix-specific meaning that's commonly confused by Windows-prior users.

**The rule (Unix convention, applies on any POSIX shell including MSYS bash):**

| Directory | What goes here | Tested by |
|---|---|---|
| `~/bin/`, `~/.local/bin/`, `/usr/local/bin/` | **Directly executable** programs invoked by name (in `$PATH`) | Typing `name` from any shell runs them |
| `scripts/`, `lib/`, `python/` | **Sourced or imported** code that defines functions/classes | Requires `source scripts/foo.sh` or `import foo` |

**Practical examples from the user's home:**

- `~/bin/pass` — pass CLI binary, directly executable, must be in `$PATH` for `pass show` to work from anywhere. **Stays in bin/**
- `~/.hermes/bin/hermes-env-load.sh` — sourced by launcher scripts; defines shell functions. **Wrongly placed** (should be in `scripts/` if it were canonically organized), but kept in `bin/` for discoverability alongside other one-shot executables
- `~/.hermes/scripts/obsidian-api.sh` — defines 16 bash functions (`obs_get`, `obs_search`, etc.) meant to be `source`d. **Correctly placed**
- `~/.hermes/bin/hermes-automation-register.ps1` — invoked once by `schtasks /Create` with `bash.exe` arg. **Correctly placed** (binary-ish from Windows Task Scheduler's POV)
- `~/.hermes/bin/hermes-vault-push.sh` + `~/.hermes/bin/hermes-vault-push-register.ps1` — pair where `.sh` is the real logic and `.ps1` registers it as a scheduled task. Both are in `bin/` because the canonical `obsidian-vault-push` skill treats them as a CLI pair

**The audit signal:** if a file in `bin/` defines shell functions (not just runs commands end-to-end), it's miscategorized. Move it to `scripts/` and update any `bash /c/Users/somew/.hermes/bin/<file>` references. If a file in `scripts/` is invoked by a Windows Task Scheduler task or a systemd timer or a launchd plist, move it to `bin/`.

**The test for "is this miscategorized":**

```bash
# If this returns 0, the file defines shell functions and is miscategorized in bin/:
grep -lE '^[a-z_]+\s*\(\s*\)\s*\{' ~/.hermes/bin/* 2>/dev/null
# If this returns 0, the file is invoked once end-to-end and is miscategorized in scripts/:
grep -lE '^[^#]*$0' ~/.hermes/scripts/* 2>/dev/null && \
  for f in $(grep -lE '^[^#]*$0' ~/.hermes/scripts/* 2>/dev/null); do
    grep -qE 'register-task|schtasks|crontab|launchctl|systemctl' "$f" || continue
    echo "  $f might belong in bin/"
  done
```

These are heuristic checks; the actual rule is "what's the call site?" — if `bash $f arg` is the only call site and the file is in `scripts/`, it's miscategorized.

### P14. The sync script's `git pull --rebase` step silently fails when the working tree is dirty (NEW 2026-07-03)

**Symptom:** `git pull origin main --rebase` fails with `error: cannot pull with rebase: You have unstaged changes.` but the script continues with "WARN: pull failed, continuing with local state." Result: the sync may push stale state, skipping commits that were made on origin since the working copy was last in sync with origin.

**Fix — there's no good reason to do `git pull` mid-sync.** If the sync script runs as a daily cron, the working tree should be reasonably clean from the previous sync's commit. Pre-flight: `git fetch origin` instead of `git pull --rebase` (or `git pull --ff-only` for safety), and skip the rebase attempt entirely if the local branch has diverged from origin.

Also: the error log line is currently misleading — change to:

```bash
log "  WARN: pull rebase failed (likely local changes); consider 'git pull origin main --ff-only' after committing"
exit 0   # or set a flag and continue, but make it explicit
```

The bigger lesson: a sync script should never assume the working tree is clean. Add a pre-flight check. The fact that the user's 2026-07-03 sync had to be killed mid-flight was partly because the dirty tree from the prior pushed commit blocked the pull — circular.

### P15. Bash heredoc + `python - "$path"` needs the path in Windows-native form, not MSYS form (NEW 2026-07-11)

**Symptom:** Your bash script does:

```bash
USER_KEY="/c/Users/somew/.hermes/security/foo.key"
"$PY" - "$USER_KEY" <<'PYEOF'
import sys
key_path = sys.argv[1]
with open(key_path, "rb") as fp:        # ← raises FileNotFoundError
    ...
PYEOF
```

…and `python` fails with `FileNotFoundError: '/c/Users/somew/.hermes/security/foo.key'`, even though the file exists and bash happily created it at that exact path.

**Root cause — three path domains, three different conventions:**

| Tool that reads the path | What it wants on Windows |
|---|---|
| git-bash / MSYS bash | `/c/Users/foo` (POSIX) — the MSYS auto-translated form |
| Native Windows Python (`C:\Program Files\Python311\python.exe`, the kind that ships in git-bash's `usr/bin/python.exe`) | `C:\Users\foo` (Windows-style with drive letter) |
| git-bash `python.exe` symlink in git-bash's `usr/bin/` | Either form works, BUT only because it's a git-bash process — outside git-bash it doesn't |

bash happily creates the key at `/c/...` because git-bash auto-translates that to `C:\...` for the actual `open()` syscall. But when you hand the literal string `/c/...` to native Windows Python, Python's `Path('C:\\')` resolver sees the leading slash as "relative path with forward slashes on the current drive" and looks for `C:\c\Users\...` — a path that almost certainly doesn't exist.

**Fix — add a `to_native_path()` helper and use it before any path arg is handed to a non-bash tool:**

```bash
# === Path: MSYS / POSIX (bash) → Windows-native (python, curl, docker.exe) ===
to_native_path() {
    local p="$1"
    if [ -z "$p" ]; then printf '%s' ""; return 0; fi
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$p" 2>/dev/null || printf '%s' "$p"
    else
        printf '%s' "$p"   # Linux/macOS: POSIX is already native
    fi
}

# === Usage ===
USER_KEY="/c/Users/somew/.hermes/security/foo.key"
USER_KEY_NATIVE="$(to_native_path "$USER_KEY")"
"$PY" - "$USER_KEY_NATIVE" <<'PYEOF'
import sys
key_path = sys.argv[1]
with open(key_path, "rb") as fp:
    ...
PYEOF
```

**Companion rule for the inverse bridge (Python → bash):** when you run a bash subprocess from native Python (`subprocess.run(['bash', script_path, ...])` from CPython on Windows), bash needs the script path in MSYS form (`/c/Users/foo`), not Windows form (`C:\Users\foo`). The bash process is detached from any MSYS-aware parent shell, so there's no auto-translation. The diagnostic that proves this is the bug: `bash: C:Userssomewfoo: No such file or directory` (backslashes eaten — the script literally doesn't see them because they got unescaped by MSYS argument parsing before bash got them). The reverse helper (`to_bash_path`) is in the `hermes-windows-filesystem-ops` skill's `scripts/to_bash_path.py` — that one probes the bash subprocess directly to discover whether it expects MSYS or WSL style.

**Why this is a separate pitfall from P1 (hardcoded `/c/Users/somew/`):** P1 is about the path being non-portable across machines. P15 is about the path being wrong for the *consumer tool* on the *same* machine. Your script works, then doesn't, depending on whether the next line calls `cat` (bash-native, MSYS-friendly) or `python - "$path"` (Windows-native, needs Windows form).

**Anti-pattern:** passing `$HOME/some/path` (which bash resolves to `/c/Users/<user>/some/path` on MSYS, `/home/<user>/some/path` on Linux) directly to `python -`. The variable expansion still happens in bash so the path LOOKS right, but it's already in MSYS form when Python sees it.

### P16. The CPython-to-bash subprocess companion of P15 (NEW 2026-07-11)

**Symptom:** You write an ad-hoc verifier in CPython on Windows that calls a bash script:

```python
subprocess.run(["bash", "/c/Users/somew/hermes-dist/relay/tests/dry-run.sh"],
               capture_output=True, text=True)
```

…and it returns exit 127 with no stdout. The bash script exists, you can run it from git-bash directly, but Python can't find `bash`.

**Root cause:** Windows-native Python (`C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe`) doesn't have `bash` on `PATH`. The MSYS-aware `python.exe` in `C:\Program Files\Git\usr\bin\` is a different binary; even when it's the one running, the subprocess it spawns inherits the Windows PATH (no Git Bash), not the MSYS PATH.

**Fix — probe explicitly, fall back to Git Bash locations:**

```python
import shutil
from pathlib import Path

bash_path = shutil.which("bash")
if not bash_path:
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ):
        if Path(candidate).exists():
            bash_path = candidate
            break

if not bash_path:
    raise FileNotFoundError("bash not found on PATH or in standard Git Bash locations")

# Now subprocess.run([bash_path, script, ...]) works.
```

**Anti-pattern:** `subprocess.run(["bash", script])` in CPython on Windows — silent exit 127 with no error message unless you read stderr.

**Companion rule for the script path.** The bash subprocess expects POSIX paths, not Windows paths. If your script lives at `C:\Users\<user>\hermes-dist\relay\tests\dry-run.sh`, you must pass it as `/c/Users/<user>/hermes-dist/relay/tests/dry-run.sh` (the MSYS form) or `bash` will say `No such file or directory` even though the file exists.

**Companion rule for environment.** The MSYS bash subprocess does NOT inherit MSYS-aware PATH automatically. If your bash script depends on `which bash` succeeding (it shouldn't, but other tools like `openssl` may), pass `env={**os.environ, "PATH": "/usr/bin:/usr/local/bin:" + os.environ["PATH"]}` to give it the MSYS PATH. For most cases the default PATH is sufficient.

### P17. CPython verifier piping bash content via `bash -n` — text-mode CRLF injection and the stdin-pipe workaround (NEW 2026-07-11)

**Symptom:** You write an ad-hoc verifier in CPython on Windows to confirm a `bash` script is parse-clean:

```python
# BAD — produces cryptic bash syntax errors on Windows
content = Path("install-linux.sh").read_text(encoding="utf-8")
subprocess.run(["bash", "-n"], input=content, capture_output=True, text=True)
# → bash returns non-zero with:  syntax error near unexpected token `$'in\r''`
# → pointing at a `case "${OSTYPE:-}" in` line that LOOKS clean
```

…and bash reports a syntax error on a `case` statement that's syntactically correct, even though `bash -n install-linux.sh` from terminal passes. The diagnostic line `case "${OSTYPE:-}" in` has a trailing `\r` that bash can't tokenize.

**Root cause — two compounding bugs in the verifier:**

1. **`text=True` in subprocess on Windows adds CRLF to stdin.** Python opens the subprocess stdin pipe in text mode, which normalizes `\n` to `\r\n` on write. bash then sees `\r` at end-of-line and chokes in `case`/`for`/`while` compound-command boundaries.
2. **MSYS path mapping is INACTIVE in CPython-spawned bash.** Even if you pass the file path as a positional arg (`bash -n /c/Users/.../install-linux.sh`), the spawned bash is detached from any MSYS-aware parent shell, so `/c/...` doesn't resolve and bash reports "No such file or directory." (P16 covers this for script paths you pass positionally; P17 is about piping file *content* via stdin instead, which sidesteps the path problem entirely.)

**Fix — binary-mode stdin pipe, no path at all:**

```python
import subprocess
from pathlib import Path

def verify_bash_parse_clean(path: Path) -> tuple[int, str]:
    """Return (returncode, stderr) from `bash -n` over the file's content.

    Pipes file bytes via stdin (binary mode) so we never depend on MSYS
    path mapping being active in the CPython-spawned bash process.
    """
    content = path.read_bytes()
    # Defensive CRLF/LF normalization — some editors store CRLF on disk.
    content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    r = subprocess.run(
        ["bash", "-n"],
        input=content,            # bytes — text=False is the default for bytes input
        capture_output=True,      # bytes stderr
    )
    return r.returncode, r.stderr.decode("utf-8", errors="replace")

rc, err = verify_bash_parse_clean(Path("install-linux.sh"))
assert rc == 0, f"bash -n failed: {err}"
```

**Why this works when the obvious approaches fail:**

| Approach | Fails because |
|---|---|
| `subprocess.run(["bash", "-n", str(path)])` with a Windows path | MSYS path mapping inactive in CPython-spawned bash |
| `subprocess.run(["bash", "-n", to_posix(path)])` with `/c/...` form | Same — the spawned bash has no MSYS mount table |
| `subprocess.run(["bash", "-n"], input=text, text=True)` | Python text-mode adds CRLF, bash chokes on `\r` |
| `subprocess.run(["bash", "-n"], input=bytes)` (the fix) | bash -n reads stdin, parses whatever's there, no path translation needed |

**Companion rule for `powershell.exe` / `pwsh` tokenize.** On Windows the same trick works for `.ps1` via `[System.Management.Automation.PSParser]::Tokenize` — that API doesn't need a path mapping, it parses a string. From CPython: `subprocess.run(["powershell", "-NoProfile", "-Command", f'$null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw "{path}"), [ref]$null); "OK"'])`. Note: this script writes `OK` to stdout if and only if tokenize succeeds; the verifier reads stdout for that marker.

**Why `pwsh` vs `powershell` matters.** `pwsh` (PowerShell 7+) is not always installed. `powershell.exe` (Windows PowerShell 5.1) ships with Windows 10+ and has `PSParser` natively. `PSParser` was officially deprecated in favor of `Ast` in newer versions, but it still tokenizes correctly on 5.1 — and "tokenize" is all you need for parse-clean verification. If `pwsh` IS available, prefer it; if not, `powershell.exe` works.

**Companion rule for cleaning up the temp verifier.** An ad-hoc verifier under `C:\Users\<user>\AppData\Local\Temp\` with a `hermes-verify-` prefix is the convention — write it, run it, `os.remove()` it after. Self-cleaning scripts leave no on-disk footprint, which matches the "ad-hoc, not part of any suite" framing.

**Anti-pattern:** leaving a `verifier.py` checked into the repo with no marker that it's ad-hoc. Future agents will run it as if it were a test suite and get confused when it diverges from canonical CI. The convention is: temp file with `hermes-` prefix, run once, delete, summarize the result in the parent session — not commit the verifier.

### P18. OS-specific installer must guard against being run on the wrong OS — the OSTYPE symmetry rule (NEW 2026-07-11)

**Symptom:** You write three installers — `install-linux.sh`, `install-macos.sh`, `install-windows.ps1` — each intended for one OS. The macOS and Windows installers have an explicit OS guard at the top (`case "${OSTYPE:-}" in darwin*) ;; ... ;; esac` and `$env:OS -eq "Windows_NT"` respectively). The Linux installer does NOT — it just runs `set -euo pipefail` and dives into prereq checks. A user on macOS who accidentally `curl | bash install-linux.sh` runs the Linux installer on macOS, fails partway through with a confusing `apt-get: command not found`, and leaves half-installed state.

**Fix — symmetry rule: every OS-specific installer has the same `case "${OSTYPE:-}"` guard, and each guard names the OTHER installers:**

```bash
# install-linux.sh — top of file
set -euo pipefail

case "${OSTYPE:-}" in
    linux*|linux-gnu*)
        ;;  # good — actual Linux
    darwin*)
        echo "✗ install-linux.sh: detected macOS (OSTYPE='${OSTYPE}')." >&2
        echo "  Use install-macos.sh instead." >&2
        exit 1
        ;;
    msys*|cygwin*)
        echo "✗ install-linux.sh: detected Windows MSYS (OSTYPE='${OSTYPE}')." >&2
        echo "  Use install-windows.ps1 instead." >&2
        exit 1
        ;;
    *)
        echo "✗ install-linux.sh: unsupported OS '${OSTYPE:-unknown}'." >&2
        echo "  Use install-macos.sh or install-windows.ps1." >&2
        exit 1
        ;;
esac
```

The matching guards in `install-macos.sh` and `install-windows.ps1` follow the same shape — `linux*` says "use install-linux.sh", `msys*|cygwin*` says "use install-windows.ps1", etc. Each guard is the inverse of the others' allowlists.

**Why the guard belongs BEFORE `set -euo pipefail`-protected work, not after:**

- `set -euo pipefail` makes any subsequent failure abort, but the abort message will be the *symptom* (missing prereq, wrong OS-specific command), not the *cause* (wrong installer).
- An explicit OSTYPE guard fails fast with a clear "you ran the wrong installer, run this one instead" message. The user sees the redirect before any state changes.

**PowerShell equivalent for `install-windows.ps1`:**

```powershell
if (-not $IsWindows -and -not ($env:OS -eq "Windows_NT")) {
    Write-Host "✗ install-windows.ps1 must be run on Windows." -ForegroundColor Red
    Write-Host "  On macOS use install-macos.sh; on Linux use install-linux.sh." -ForegroundColor Red
    exit 1
}
```

`$IsWindows` is the PowerShell 7+ automatic variable; on Windows PowerShell 5.1 (the version that's reliably installed on Windows 10+), `$env:OS` is the canonical check. The `-or` covers both.

**Class lesson:** any time you have N OS-specific scripts (where N ≥ 2), each script should refuse to run on the other N-1 OSes with a clear message naming the right installer. This is the install-script analog of the "refuse commands outside your allowlist" rule for agents (the SOUL.md "no shell access" principle, applied to the install script itself).

## The interaction with install/install.sh

`install/install.sh` in the OCD repo uses a slightly extended version
of this pattern with per-OS prereq install (`scoop` / `brew` / `apt`)
and per-OS prereq verification (`brew --version`, `scoop --version`).
See `references/install-sh-ostype-pattern.md` for the install-script
extension.

## The pattern's relationship to existing skills

- **`session`** — session-open/close discipline. Complements
  this skill: ritual covers "what to check at session start", this skill
  covers "how to write code that survives the next session's check".
- **`windows-wsl2-hermes`** — Windows-specific config gotchas (path
  translation, MSYS quirks). Use when debugging Windows-specific failures.
- **`hermes-skill-authoring`** — how to write a SKILL.md. Different scope.
- **`hermes-skill-refactor`** — how to trim a SKILL.md. Use after this skill's
  examples accumulate in a real script.

## Bundled references

- `references/install-sh-ostype-pattern.md` — the install/install.sh
  extension that uses this pattern for prereq install + per-OS verify.
- `references/launchd-plist-template.md` — copy-paste Mac launchd plist
  with all the right keys.
- `references/systemd-user-timer-template.md` — copy-paste Linux
  systemd user timer + service pair.

## Bundled scripts

- `scripts/cross-platform-init.sh` — a reference implementation of the
  pattern in §2 + §3 + §4 that you can copy into a new script. Reads
  the OSTYPE case, sets _USER_DIR + _HERMES_EXE_SUBDIR + _HERMES_EXE_NAME,
  and writes a usage example.
- `scripts/sanity-check.sh` — quick lint for an existing script: greps
  for hardcoded `/c/Users/somew/`, unguarded `cmd //c`, `hermes.exe`
  literals, and unquoted heredoc markers. Run before committing any new
  bash script under `$HERMES_HOME/scripts/`.
</content>