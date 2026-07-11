# Desktop "fresh install" trap — when wiping apps/desktop isn't enough

**Captured:** 2026-07-02, this host (Windows 10, Hermes Agent v0.18.0).
**Class of failure:** User says "kill and remove ALL rememence of herems desktop and the current install". You wipe `apps/desktop/{dist,release,.vite,node_modules/.vite,tsconfig.tsbuildinfo}` and `~/.hermes/{desktop,desktop.json}`, rebuild the release, and the user reports the SAME error in one window while another works. Or: "two instances, same source, different behavior" — a clean signal that you missed one of the locations below.

## Why a "fresh install" needs more than `apps/desktop`

Hermes Desktop is a regular Electron app. Its runtime state lives in **three** locations, not one:

| Layer | Path | Wiped by `hermes update`? |
|---|---|---|
| Source checkout | `C:\Users\somew\.hermes\hermes-agent\apps\desktop\` | yes |
| Build outputs | `apps/desktop/dist/` (vite), `apps/desktop/release/win-unpacked/Hermes.exe` (electron-builder), `.vite`, `node_modules/.vite`, `tsconfig.tsbuildinfo` | yes (rebuilt) |
| Electron `userData` / cache | `C:\Users\<user>\AppData\Roaming\hermes-desktop\` (Chromium cache, Service Workers, IndexedDB, session state) | **NO — never touched by install/update** |
| Updater state | `C:\Users\<user>\AppData\Local\hermes-desktop-updater\` | **NO** |
| **Separately installed copy** | `C:\Users\<user>\AppData\Local\Programs\hermes-desktop\hermes-agent.exe` (pre-`hermes-agent`-vcs layout — installed via the Hermes MSI/installer before the user moved to the git checkout) | **NO** |
| Old binary shadow copies | `C:\Users\<user>\AppData\Local\Temp\hermes-asar\` | **NO** |

If any of the bottom three exist, you have **two physically separate Hermes Desktop apps** on the machine:

- The git-built one at `apps\desktop\release\win-unpacked\Hermes.exe` (clean state, fixed).
- The MSI-installed one at `AppData\Local\Programs\hermes-desktop\hermes-agent.exe` (stale, broken, may still claim `app-user-model-id=com.hermes.desktop`).

The shortcut on the desktop (`Desktop\Hermes One.lnk` or `Desktop\Hermes.lnk`) can point at EITHER. Same `hermes desktop` CLI invocation can spawn EITHER, depending on `HERMES_DESKTOP_HERMES_ROOT` and the desktop's own `--hermes-root` resolver. Two windows → two different code paths → two different outcomes per slash command.

## The "Duplicate slash command alias: /compact" upstream bug (real, not a backend symptom)

There's also a **real catalog collision** that's easy to misdiagnose as "backend down":

- Upstream commit `ce9aa869f feat(commands): /compact alias + --preview/--dry-run flags for /compress` (Jul 2 2026, on the Hermes CLI side) added `/compact` as an alias of `/compress`.
- The desktop's local stub list at `apps/desktop/src/lib/desktop-slash-commands.ts` (line 183 in that commit) still listed `/compact` in `NO_DESKTOP_SURFACE.terminal` as a standalone "terminal-only" command.
- When the desktop merges its stub list with the live backend catalog, `/compact` ends up registered TWICE — once as an alias-target of `/compress` (exec surface), once as a terminal-only command. The dedup check fires.

This collides with the well-known "backend down → empty catalog → fallback stub → alias dedup" pattern (see `references/desktop-backend-required-2026-07-02.md`). Different cause, same symptom. **Fix the backend FIRST**, then if the warning persists on a clean connection, this is the actual bug.

### The fix (until upstream ships one)

Two edits in `apps/desktop/src/lib/desktop-slash-commands.ts`:

1. Remove `'/compact'` from the `terminal: [...]` array in `NO_DESKTOP_SURFACE`.
2. Add `aliases: ['/compact']` to the `/compress` entry in `DESKTOP_COMMAND_SPECS` (so it routes to exec surface and the alias-hiding logic at line ~300 keeps it out of the popover).

Regression test additions in `apps/desktop/src/lib/desktop-slash-commands.test.ts`:

```ts
expect(isDesktopSlashSuggestion('/compact')).toBe(false)
expect(isDesktopSlashCommand('/compact')).toBe(true)
expect(resolveDesktopCommand('/compact')?.surface).toEqual({ kind: 'exec' })
expect(desktopSlashUnavailableMessage('/compact')).toBeNull()
```

All 15 tests pass after the patch. 15 was the count before; the patch is additive within the existing "hides terminal…" test.

## Build requirement that bites `--skip-build`

`hermes desktop --skip-build` does NOT use `apps/desktop/dist/`. It launches from `apps/desktop/release/win-unpacked/Hermes.exe`, which is produced by `npm run pack` (which runs `build` then `electron-builder --dir`). If you've only run `npm run build` and wiped `release/`, the launcher errors:

```
✗ --skip-build was passed but no packaged desktop app was found at:
  C:\Users\somew\.hermes\hermes-agent\apps\desktop\release
  Pre-build first:  cd apps/desktop && npm run pack
  Or drop --skip-build to package automatically.
```

`npm run pack` is mandatory after any source edit + before `--skip-build` will work.

## The full "desktop fresh install" recipe

In order — do NOT skip the Electron userData step:

1. Kill all Hermes.exe desktop processes from BOTH the git release dir AND `AppData\Local\Programs\hermes-desktop\`:

   ```bash
   # 1a. git-release desktop (the one you just built)
   powershell "Get-Process -Name Hermes |
     Where-Object { $_.MainModule.FileName -like '*apps\desktop\release\win-unpacked\Hermes.exe' } |
     ForEach-Object { Stop-Process -Id \$_.Id -Force }"

   # 1b. MSI-installed desktop (the trap)
   powershell "Get-CimInstance Win32_Process |
     Where-Object { $_.CommandLine -match 'AppData\\Local\\Programs\\hermes-desktop' } |
     ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
   ```

2. Stop backend: `hermes serve --stop` (kills the local listener on :9119). Verify with `netstat -an | grep 9119` → empty.

3. Wipe build artifacts:

   ```bash
   rm -rf /c/Users/somew/.hermes/hermes-agent/apps/desktop/{dist,release,.vite,node_modules/.vite}
   rm -f  /c/Users/somew/.hermes/hermes-agent/apps/desktop/tsconfig.tsbuildinfo
   ```

4. Wipe Electron userData + updater state (the easy-to-miss bit):

   ```bash
   rm -rf "/c/Users/somew/AppData/Roaming/hermes-desktop"
   rm -rf "/c/Users/somew/AppData/Roaming/Hermes"
   rm -rf "/c/Users/somew/AppData/Local/hermes-desktop-updater"
   rm -rf "/c/Users/somew/AppData/Local/Temp/hermes-asar"
   ```

5. **Wipe the separately-installed copy** (the OTHER trap):

   ```bash
   rm -rf "/c/Users/somew/AppData/Local/Programs/hermes-desktop"
   ```

   If you skip this, your desktop shortcut and Start Menu entry will keep launching the broken old copy even after you fix the git build.

6. Wipe Hermes-side desktop state:

   ```bash
   rm -rf /c/Users/somew/hermes/desktop*
   rm -f  /c/Users/somew/.hermes/logs/desktop*.log
   ```

7. Apply any source fixes, then rebuild packaged release:

   ```bash
   cd /c/Users/somew/.hermes/hermes-agent/apps/desktop
   npm run pack          # NOT `npm run build` alone — needs electron-builder
   ```

8. Rewrite the Desktop shortcut to point at the fresh exe (in case the OS shortcut still references the MSI copy):

   ```bash
   powershell '$ws = New-Object -ComObject WScript.Shell
   $s = $ws.CreateShortcut("$env:USERPROFILE\Desktop\Hermes One.lnk")
   $s.TargetPath = "C:\Users\somew\.hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe"
   $s.WorkingDirectory = "C:\Users\somew\.hermes\hermes-agent\apps\desktop\release\win-unpacked"
   $s.Arguments = ""
   $s.Save()'
   ```

9. Start backend, launch desktop:

   ```bash
   hermes serve --skip-build --port 9119   # background
   "/c/Users/somew/.hermes/hermes-agent/apps/desktop/release/win-unpacked/Hermes.exe" &
   ```

10. Verify exactly one desktop process tree, one listener, one bundle:

    ```bash
    tasklist | grep -i 'Hermes.exe'
    # Expect: all Hermes.exe processes have CommandLine pointing at
    # apps/desktop/release/win-unpacked/Hermes.exe — NO AppData\Local\Programs\hermes-desktop\hermes-agent.exe.
    netstat -an | grep 9119
    # Expect: ONE PID listening.
    ```

## Diagnostic for "two instances, same source, different behavior"

If the user reports "this window works, that window doesn't":

```bash
powershell "Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'Hermes.exe|hermes-agent.exe' } |
  Select-Object ProcessId,Name,@{n='Bin';e={$_.CommandLine.Substring(0,
    [Math]::Min(100, $_.CommandLine.Length))}}"
```

If you see ANY `hermes-agent.exe` under `AppData\Local\Programs\hermes-desktop\`, that's the old install. Wipe it (step 5 above) and have the user relaunch from the shortcut.

## Pitfalls

- **Don't trust `npm run build` to be enough.** It produces `dist/` for vite but the desktop is an Electron app — it needs `release/win-unpacked/Hermes.exe` from `npm run pack`.
- **Don't trust `hermes serve --stop` to kill the GUI-side backend.** It only kills the dashboard processes it tracks. The desktop's bundled serve (or a separately-spawned one) keeps running until you `Stop-Process` the owning PID via `Get-NetTCPConnection -LocalPort 9119`.
- **Don't trust the shortcut on Desktop to track your build.** It points to whatever was the latest installed `Hermes.exe` at shortcut-creation time. After wiping the install, regenerate the shortcut (step 8).
- **Don't wipe `apps/desktop/src/` to "fully remove" the desktop.** It's source checked into the git checkout — `hermes update` will re-install it. The user wanted a clean *runtime*, not to delete the source tree.
- **Don't claim a fix worked without checking the renderer.** The Electron renderer console is separate from `gui.log`. The dedup warning fires in the renderer; you'll only see it via the user / DevTools / a websocket frame inspection.
- **Don't repeatedly re-derive the same debug tree.** If the first 3 tool calls didn't show you what's different, the user's "two instances" hint is a STRONG signal that the answer is in `Get-CimInstance Win32_Process` — stop guessing and run that exact probe.