# Desktop backend listener required (2026-07-02)

## Class of failure

`hermes desktop` is a **thin Electron client** that talks to a **separately
running JSON-RPC/WebSocket backend** (`hermes serve`, default port 9119).
The desktop launcher does NOT auto-spawn the backend. If the backend is
down, the desktop will:

- Launch its UI window (looks fine at first glance)
- Render the chat composer and message list
- Surface every gateway RPC failure as `Error: read ECONNRESET` in the
  Electron console
- Show an empty slash-command popover, or trigger spurious
  "Duplicate slash command alias" warnings

The "duplicate alias" message is a **downstream symptom**, not the bug.
When the desktop's `commands.catalog` RPC fails, it falls back to a
local-only stub list; that stub list can collide with the TUI's local
slash command registry (e.g. both register `/compact`), and the dedup
warning fires. Fix the backend and the alias collision goes away.

## The diagnostic that pinpoints it in 5 seconds

```bash
netstat -an | grep 9119
# Empty output = backend is down, regardless of what the desktop UI shows.
```

The chat composer is local React state. The slash popover is local
state. The connection only matters once you submit a prompt or query
the command catalog. So the UI lies. The listener doesn't.

## The three-step recovery

```bash
# 1. Start the backend (long-lived; use terminal(background=true)).
hermes serve --skip-build --port 9119

# 2. Verify readiness BEFORE launching the desktop.
curl -s http://127.0.0.1:9119/healthz
# 200 = backend serving. Anything else = wait or check logs.

# 3. Now launch the desktop.
hermes desktop --skip-build
```

`--skip-build` is critical: without it the desktop launcher will run
`npm run build` (vite + tsc + native-deps staging) which takes 30-60
seconds and may not be necessary if `dist/` already exists from a
prior build. The desktop is pre-bundled; rebuild is only needed after
you change something under `apps/desktop/src/`.

## Why this isn't documented elsewhere in the skill library

The `hermes-agent` bundled skill mentions `hermes serve` exists but
doesn't say "the desktop requires it to be running first." The
`session` skill covers `hermes cron status` and gateway
health for cron jobs, but doesn't mention the desktop gateway. The
`hermes-session-open-inventory` skill covered plugin venv alignment
(Step 2.5) and profile alias lifecycle (Step 2.55 didn't exist
before this incident) but not the desktop backend. This reference
file closes the gap.

## Full incident transcript (this user, 2026-07-02)

User reported three things:
1. Mnemosyne memory provider "active" but "not available"
2. Hermes Desktop launches but slash commands fail with "Duplicate
   slash command alias: /compact"
3. Orphan alias warnings in `hermes doctor` for two deleted profiles

Investigation order that worked (reverse the order if you hit this
fresh — the bug is the desktop backend being down, the venv mismatch
is separate):

1. **Orphan aliases** (5 min): confirmed the .bat wrappers live in
   `~/.local/bin/`, not `~/.hermes/profiles/`. Deleted both with
   `rm`. Easy.

2. **Mnemosyne unavailable** (20 min): traced to `pip install mnemosyne`
   having gone to the wrong venv. PATH `pip` was bound to
   `C:\Users\somew\llama.cpp\env\Scripts\pip.exe` (a different venv
   used for local model serving), NOT Hermes's own
   `C:\Users\somew\.hermes\hermes-agent\venv\Scripts\pip3.11.exe`.
   First `pip install mnemosyne` pulled a 5 kB placeholder package
   whose top-level name shadowed the real `mnemosyne-hermes` distribution,
   causing a secondary "No module named 'mnemosyne.core.beam'" error.
   Uninstall placeholder, install `mnemosyne-hermes` (which pulls
   `mnemosyne-memory>=3.1`), confirm with a `from mnemosyne.core.beam
   import BeamMemory` test. Solved.

3. **Desktop slash commands** (15 min, should have been step 0): the
   duplicate-alias error was the most visible symptom but the actual
   cause was the desktop backend not running. `hermes serve --status`
   returned "No hermes dashboard processes running." Started
   `hermes serve --skip-build --port 9119` in the background, confirmed
   `127.0.0.1:9119 LISTENING`, re-launched Electron, no more ECONNRESETs,
   slash commands worked.

**Time wasted in step 3 (~15 min):** I went hunting through
`acp_adapter/server.py`, `ui-tui/src/app/slash/commands/core.ts`,
`apps/desktop/src/lib/desktop-slash-commands.ts`, and the
`tui_gateway/server.py commands.catalog` RPC looking for an actual
`/compact` double-registration. There IS one (the real Hermes bug is
at `hermes_cli/commands.py:92` where `compress` has `aliases=("compact",)`
which collides with ACP's separately-registered `compact`), but it
wasn't what was triggering the user-visible error. The user-visible
error was the backend being down.

**Better order for the next agent:**
1. `netstat -an | grep 9119` — first, every time, before debugging
   anything slash-command-related on the desktop.
2. Then the plugin-venv alignment probe (Step 2.5).
3. Then the slash-command registration audit.

## Three rules to remember

- **The chat composer lies about backend health.** Always probe `:9119`.
- **"Duplicate slash command alias" is rarely a real registration
  collision** — it's almost always the desktop falling back to local
  stubs because the backend's `commands.catalog` is unreachable.
- **`hermes serve --skip-build` is the right startup command** when
  `dist/` already exists. Skip the 30-60 second rebuild.
