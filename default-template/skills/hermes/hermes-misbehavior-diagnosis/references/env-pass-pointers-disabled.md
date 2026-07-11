---
name: env-pass-pointers-disabled
description: Why the .env pass: pointers in ~/.hermes/.env lines 487-494 are intentionally disabled, and the proper secret-resolution architecture (hermes-env-load.sh + secrets-spec.json). Use when the symptom is "literal pass:api/X in env" or "No bot token configured" — do NOT recommend uncommenting the .env pass: pointers as a fix. Verified 2026-07-09.
---

# Why `~/.hermes/.env` `pass:` pointers are disabled (this user)

**Hard rule (user-confirmed 2026-07-09):** the 8 lines at `~/.hermes/.env:487-494`
(`# OPENROUTER_API_KEY=*** `# HERMES_SPOTIFY_CLIENT_ID=pass:api/spotify-client-id`,
`# TELEGRAM_BOT_TOKEN=*** `# DISCORD_BOT_TOKEN=*** `# MINIMAX_API_KEY=*** `# MNEMOSYNE_LLM_API_KEY=*** `# API_SERVER_KEY=pass:api/server-key`,
`# CIVITAI_API_KEY=***`) are **intentionally commented out**. Uncommenting
them causes the agent to **hang or timeout** at hermes boot.

**User pushback verbatim** when the agent (this session, 2026-07-09) recommended
uncommenting as a fix: *"remebmeer this now that was never the root cause, it
because of other issue in order for u to work we had to commeent them out to
not hang or timeout"*. This was a SECOND INSTANCE of the v2.7.0
`predict-without-testing` anti-pattern in the same day — the earlier instance
(the 2026-07-09 morning) was the same misdiagnosis from a different session,
also corrected by the user.

**The 3-layer secret-resolution architecture on this host:**

```
  Layer 1: ~/.hermes/.env (DISABLED by user — uncommenting hangs)
              ↓ if enabled, would be the canonical place
  Layer 2: ~/.hermes/secrets-spec.json (canonical mapping)
              ↓ source via ~/.hermes/bin/hermes-env-load.sh
  Layer 3: ~/.hermes/bin/hermes-env-load.sh (the bridge)
              ↓ calls `pass show` per mapping
              ↓ exports to current shell's os.environ
  Result: tokens live in the LAUNCH SHELL'S os.environ
              ↓ inherited by child processes
  Consumer: hermes_cli.main gateway run (the proper daemon)
              ↓ reads os.environ.get('DISCORD_BOT_TOKEN') etc.
              ↓ connects to platforms
```

**Where the actual fix lives for "No bot token configured" symptoms:**

1. **Verify the launch shell sourced `hermes-env-load.sh` BEFORE the proper
   daemon was spawned.** The proper daemon (argv = `pythonw.exe -m
   hermes_cli.main gateway run`) is a fresh Python process — it inherits
   `os.environ` from its parent shell. If the parent shell didn't have the
   tokens, the daemon doesn't have them. The proper daemon does NOT call
   `pass show` itself — that work is done by the launcher, not the daemon.

2. **Check the parent shell's `os.environ` for the tokens.** The classic
   diagnostic: from the same shell that launched the daemon, run
   `printenv | grep -E 'TELEGRAM_BOT_TOKEN|DISCORD_BOT_TOKEN|OPENROUTER_API_KEY'`.
   If those are `<UNSET>`, the loader was never sourced (or was sourced in
   a different shell).

3. **Check `~/.hermes/secrets-spec.json` matches `~/.password-store/api/`.**
   The spec has 8 mappings; the vault has 7 `.gpg` files
   (civitai, discord-bot, minimax, mnemosyne-llm, openrouter, server-key,
   spotify-client-id). **Telegram is missing from the vault** —
   `~/.password-store/api/telegram-bot.gpg` does not exist. So the loader
   will skip `TELEGRAM_BOT_TOKEN` with a "pass entry not found" warning,
   and the gateway will still log "No bot token configured" for Telegram
   even after the loader is sourced. This is correct behavior, not a bug.

4. **Verify the loader is sourced in the user's normal shell init.** The
   loader should be sourced from `~/.bashrc` (or whatever the user's
   interactive shell rc is) so that every new shell session gets the
   tokens automatically. As of 2026-07-09 it is NOT auto-sourced — the
   user sources it manually per session. If the user wants it auto-sourced,
   add `source ~/.hermes/bin/hermes-env-load.sh` to `~/.bashrc` (gated
   behind `[[ -f ~/.hermes/secrets-spec.json ]]` and possibly a
   `HERMES_LOAD_SECRETS` opt-in flag to avoid the GPG prompt on every
   new tab).

5. **For the proper daemon launched as a scheduled task** (`\Hermes_Gateway`):
   the task's `Actions[0].Execute` must source the loader before launching
   the daemon. The current scheduled task points at
   `Hermes_Gateway.cmd → resolve-and-launch-gateway.sh`, neither of which
   sources the loader — the task is broken from a token-resolution
   perspective. See `references/gateway-daemon-binary-override.md` for
   the full scheduled-task fix recipe.

## Why the .env pass: pointers were disabled

The user's pre-2026-07-05 setup had `KEY=pass:api/X` lines uncommented in
`~/.hermes/.env` and used `hermes_cli.env_loader.load_hermes_dotenv()`'s
in-process pass resolver to populate `os.environ` from the pass vault at
boot. This worked until a 2026-07-05 incident (memory entry
`fce4088a41598287` documents it; the `trash/2026-07-05-0954/orig-hermes-secrets-env.sh`
file is the deleted loader from that day) where the agent hung at boot
on the `pass show` calls — most likely the GPG agent was locked and
`pass show` blocked waiting for a passphrase, but the shell-init context
had no way to prompt the user. The user worked around the hang by
commenting out the `pass:` pointers in `.env` and switching to a
**per-session, manual `source hermes-env-load.sh`** model. The GPG prompt
is acceptable when the user types the source command themselves; it is
unacceptable when it blocks hermes boot silently.

The trade-off: hermes no longer auto-resolves pass pointers at boot. The
launch shell must explicitly source the loader. For manual `hermes chat`
sessions, the user sources the loader in their shell tab before
launching. For the proper daemon (gateway), the launch context (scheduled
task, terminal session, or programmatic spawn) must do the same.

## The "hermes gateway start" trap

`hermes gateway start` does NOT source `hermes-env-load.sh` itself. It
spawns `pythonw.exe -m hermes_cli.main gateway run` directly, inheriting
the current shell's `os.environ`. If the current shell doesn't have the
tokens, the spawned daemon doesn't have the tokens. The fix is **NOT** to
add the loader-sourcing logic to `hermes gateway start` — the design
intent (per the loader's own docstring) is "the user runs `source
hermes-env-load.sh` once per session; secrets land in `os.environ` for the
duration of the shell session only."

**The trap:** the legacy daemon (`scripts/hermes-gateway`) accidentally
worked for token resolution because it inherited the parent shell's
`os.environ` (which the user had pre-set somewhere). The proper daemon
(`hermes_cli.main gateway run`) is functionally identical for
`os.environ` inheritance — the bug is that the launch shell doesn't
HAVE the tokens to inherit. The fix is the launch shell, not the daemon.

## `gateway_state.json` staleness wart (separate from daemon-binary-override)

`hermes gateway stop` and `hermes gateway start` do NOT refresh
`~/.hermes/gateway_state.json`. After a stop+start cycle, the state file
will still show the OLD pid and OLD argv. The state file is updated by
the daemon itself on its OWN startup — if the new daemon doesn't write
to the state file, the file stays stale forever.

**Workaround:** when verifying which daemon binary is running, use
`Get-CimInstance Win32_Process` (live process table) to check the
CommandLine of the actual running pid, not just the state file. The
state file is "what was launched last" — the live process is "what's
running now." They can diverge.

**Companion:** `references/gateway-daemon-binary-override.md` covers the
PROPER vs LEGACY daemon distinction. This reference covers the LAUNCH
CONTEXT (the shell that spawns the daemon) which is a different layer
but contributes to the same symptom class.

## Verification recipe — "is the launch context correctly tokenized?"

```bash
# From the SAME shell that launched the proper daemon:

# 1. Are the tokens set in this shell?
printenv | grep -E 'TELEGRAM_BOT_TOKEN|DISCORD_BOT_TOKEN|OPENROUTER_API_KEY|API_SERVER_KEY|MINIMAX_API_KEY|CIVITAI_API_KEY|HERMES_SPOTIFY_CLIENT_ID'
# Expect: 7 lines (or 6 if Telegram is missing from the vault and the
# loader skipped it with a "pass entry not found" warning)

# 2. Did the proper daemon inherit them?
# (requires the daemon's pid — from `tasklist /FI "IMAGENAME eq pythonw.exe"`)
powershell -Command "
Get-CimInstance Win32_Process -Filter 'Name=\"pythonw.exe\"' |
  Where-Object { \$_.CommandLine -like '*hermes_cli.main*' } |
  ForEach-Object { Write-Host \"pid=\$(\$_.ProcessId) parent=\$(\$_.ParentProcessId) command=\$(\$_.CommandLine)\" }
"
# Expect: at least one pythonw.exe with -m hermes_cli.main gateway run

# 3. Is the gateway log showing connect attempts?
tail -n 50 ~/.hermes/logs/gateway-stdout.err.log | grep -E 'connected|No bot token|invalid_token'
# Expect: '✓ discord connected', 'No bot token configured' for Telegram
# (Telegram is the expected-UNSET one — the gpg is missing)

# 4. If Discord is also "No bot token", the launch shell didn't have the
#    tokens. Fix: source ~/.hermes/bin/hermes-env-load.sh, then
#    hermes gateway stop && hermes gateway start.
```

## When to use this reference

- Symptom: `gateway-stdout.err.log` shows repeated "No bot token configured"
  for Discord / Telegram / etc.
- Symptom: `gateway-stdout.err.log` shows literal `pass:api/X` strings
  reaching the platform's auth call (the "literal pointer" class).
- Symptom: user reports "the agent receives the pointer string instead
  of the secret" — and the agent is about to recommend uncommenting the
  .env pass: pointers. STOP. Read this reference first.
- Workflow: about to relaunch the proper daemon. Verify the launch shell
  has the tokens BEFORE spawning the daemon, not after.

## When NOT to use this reference

- The `pass vault: applied 0 secrets` line appears in the log AND the
  .env has uncommented `KEY=pass:api/X` lines AND the agent's Recipe B
  returns `applied = 0` with warnings about missing .gpg files. That's
  a different bug (GPG lock, missing pass binary on PATH, or missing
  vault entries) — not the .env-disabled issue.
- The platform is connecting fine and the user is asking about a
  different layer (provider API key, model selection, etc.).
- The user is on a fresh install and the pass vault hasn't been
  initialized yet. That's a setup task, not a misdiagnosis.

## Cross-references

- `hermes-misbehavior-diagnosis/SKILL.md` (the misbehavior reflex) —
  this reference is the **technical** half; the misbehavior skill
  encodes the **reflex** ("don't recommend uncommenting .env pass:
  pointers — see env-pass-pointers-disabled reference").
- `hermes-misbehavior-diagnosis/references/anti-pattern-predict-without-testing.md`
  — the v2.7.0 anti-pattern that this reference is the concrete
  counter-example for.
- `hermes-config-cli-gotchas/SKILL.md` § "`secrets:` config block" — the
  upstream's `secrets:` block semantics (the `pass` source is always-on
  by default; the `secrets.pass:` YAML is decoration).
- `hermes-config-cli-gotchas/references/pass-resolver-cold-start-test.md`
  — the diagnostic recipe for "is the resolver working in isolation."
  Use this BEFORE the env-pass-pointers-disabled reference to confirm
  the .env content is or isn't the issue.
- `hermes-config-cli-gotchas/references/gateway-daemon-binary-override.md`
  — the PROPER vs LEGACY daemon distinction. This reference covers the
  LAUNCH SHELL context; the daemon-binary-override covers the
  DAEMON BINARY itself. Same symptom class, different layer.

## Changelog

- **v1.0.0 (2026-07-09, this user):** Initial creation. The hard-rule
  (.env pass: pointers disabled by user — uncommenting hangs) was
  user-confirmed in this session. The 3-layer architecture, the
  `hermes gateway start` doesn't-source-loader trap, the
  `gateway_state.json` staleness wart, and the launch-context
  verification recipe are documented for the first time.
