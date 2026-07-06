# Hermes Dist — Architecture

## System overview

```
   ┌─────────────────────────────────────┐
   │  Operator's PC (this box)           │
   │                                     │
   │  default profile                    │  ←─ operator works here, full power
   │  state.db (operator's memories)     │     never sees user data
   │                                     │
   │  collector profile                  │  ←─ pull-only quarantine
   │  state.db (review notes)            │     hard-isolated
   │  quarantine/skills/                 │
   │  quarantine/scripts/                │
   │  quarantine/memories/               │
   │                                     │
   └─────────────────┬───────────────────┘
                     │  git pull (silent)
                     │  + manual `hermes update`
                     ▼
   ┌─────────────────────────────────────┐
   │  hermes-dist repo (this dir)        │
   │                                     │
   │  default-template/  ← bundled       │
   │  relay/             ← bundled       │
   │  install-*.{ps1,sh} ← bundled       │
   │  .onboard.sh        ← bundled       │
   │                                     │
   └─────────────────┬───────────────────┘
                     │  git push (when you release)
                     ▼
   ┌─────────────────────────────────────┐
   │  GitHub (or other git host)         │
   │  github.com/you/hermes-dist         │
   │  tag: v1.0.0, v1.1.0, ...           │
   │                                     │
   └─────────────────┬───────────────────┘
                     │  user install pulls
                     │  daily cron at 09:00
                     ▼
   ┌─────────────────────────────────────┐
   │  User install (per-user)            │
   │  ~/.hermes/                         │
   │  profiles/<user_uuid>/              │
   │    SOUL.md (read-only)              │
   │    config.yaml (per-user)           │
   │    hooks/ (chmod 555)               │
   │    mnemosyne/ (per-user bank)       │
   │  audit.log (per-user)               │
   │  quarantine/ (per-user copy)        │
   │                                     │
   │  Restricted toolsets:               │
   │    [file, web, search, browser,     │
   │     vision, memory, todo, clarify,  │
   │     session_search, skills, tts,    │
   │     code_execution, image_gen,      │
   │     x_search]                       │
   │                                     │
   │  DENIED: terminal, delegation,      │
   │  cronjob, kanban, mcp, computer_use │
   │                                     │
   │  hooks/                             │
   │    pre-tool.sh       (deny-by-default at shell layer)
   │    post-skill-create.sh (denylist scan + quarantine)
   │    post-memory-save.sh  (opt-in forwarding)
   │                                     │
   └─────────────────┬───────────────────┘
                     │  HMAC-signed POSTs
                     │  (only if user opted in)
                     ▼
   ┌─────────────────────────────────────┐
   │  Oracle Cloud (Always Free ARM)     │
   │  relay.your-domain                  │
   │                                     │
   │  FastAPI + SQLite (Docker)          │
   │  Port 9119 (HTTPS recommended)      │
   │                                     │
   │  /api/v1/healthz   public           │
   │  /api/v1/register  public           │
   │  /api/v1/submit    HMAC required    │
   │  /api/v1/events    operator token   │
   │  /api/v1/users     operator token   │
   │  /api/v1/audit     operator token   │
   │                                     │
   └─────────────────────────────────────┘
```

## Data flow (one user's session)

1. User launches Hermes (CLI or desktop).
2. User asks the agent to do something (e.g. "write a script to scrape X").
3. Agent decides to call `file:write_file` to create `~/Documents/alice/scrape.py`.
4. **`pre-tool.sh` runs:**
   - Checks `file:write_file` is in the allowlist → pass
   - Checks the target path is under `~/Documents` → pass
   - Audits the call to `audit.log`
5. Agent writes the script via `write_file` (the tool executes).
6. **`post-skill-create.sh` runs** (the agent may also create a skill, e.g. a helper for the script):
   - Scans the skill's `SKILL.md` and `scripts/` against `denylist.yaml`
   - If clean: copies to `~/.hermes/quarantine/skills/clean/`, logs, forwards a signed event to the relay
   - If flagged: copies to `~/.hermes/quarantine/skills/flagged/`, deletes the local install, immediately forwards a flagged-event to the relay
7. The script the user wrote (separately, in their own files) is runnable in `code_execution` (sandboxed Python). It cannot reach the relay, cannot touch operator files, cannot read ~/.hermes.
8. If the user marks a memory with `submit_to_collector: true`:
   - **`post-memory-save.sh` runs**
   - Checks user opted in to sync (config flag)
   - If yes: writes to `~/.hermes/queue/memories/`, logs, `forward-sync.sh` POSTs to the relay with HMAC signature
   - If no: logs locally only, nothing leaves the box
9. Relay verifies HMAC, checks nonce (replay defense), checks timestamp (clock skew ±300s), stores in SQLite.
10. Operator runs `hermes-distribution pull` (or it's on a cron) to fetch new events into `collector/quarantine/`.
11. Operator launches `hermes -p collector chat` to review what's pending.
12. Operator says "approve skill X" — the collector profile moves it to `quarantine/approved/` and writes a decision to `audit/audit.log`.
13. Next time the operator bundles a release, they `cp -r collector/quarantine/approved/* ~/hermes-dist/skills/` and tag `v1.2.0`. Users running `hermes update` get the new skills on their next daily-pull + manual-update.

## Security model

### Defense in depth (in order of strength)

1. **Toolset removal (config layer):** The user's `config.yaml` doesn't list `terminal`, `delegation`, `cronjob`, etc. The agent's prompt doesn't even know those tools exist.
2. **Hook allowlist (shell layer):** Every tool call runs through `pre-tool.sh` which re-checks the allowlist from `allowlist.yaml`. A prompt-injection that somehow rewrote `config.yaml` cannot bypass this — it doesn't have write access to the hook script.
3. **Path denylist (shell layer):** `pre-tool.sh` rejects any file path under `~/.hermes`, `~/.local`, system dirs, etc. — even if the user themselves tries to write there.
4. **URL denylist (shell layer):** `pre-tool.sh` rejects `browser_navigate` and `web_extract` to private IP ranges, localhost, known exfil hosts.
5. **Script denylist (post-skill-create):** Any skill the user creates is scanned against `denylist.yaml` for prompt-injection patterns, hermes-internal imports, shell-exec calls, credential string literals, exfil endpoints. Flagged = quarantined + forwarded.
6. **HMAC auth (network layer):** Every relay-bound event is signed. Unsigned = 401. Replay = 401 (nonce store). Bad signature = 401.
7. **Operator token (network layer):** Querying events requires a separate, longer token that the operator keeps in a password manager.
8. **chmod 444 (filesystem layer):** Operator-owned files (`SOUL.md`, `denylist.yaml`, `allowlist.yaml`, hook scripts) are read-only. The user can read but not modify. Even `chmod` would be denied (no `terminal` tool).
9. **Force-pull on launch (update layer):** Every time the user launches the agent, the security files are re-pulled from the operator's repo. If you push a new denylist entry, every user gets it within 24 hours (or immediately on next launch, whichever comes first).
10. **Mnemosyne isolation (memory layer):** User's Mnemosyne bank is at `~/.hermes/profiles/<user_uuid>/mnemosyne/`. Operator's bank is at `~/.hermes/mnemosyne/`. The two are physically separate SQLite files. There is no cross-talk.

### What a hostile user CAN do

- Write any script that doesn't match the denylist, save it to their working dir
- Run that script in the `code_execution` sandbox (sandboxed: no network beyond allowlisted ports, no filesystem beyond cwd)
- Web scrape anything not in the URL denylist
- Save memories (local-only, or forwarded if marked + opted in)
- Create skills (always scanned; flagged ones quarantined)
- Read the operator's `SOUL.md` (interesting but inert — it has no authority over the user's install)

### What a hostile user CANNOT do

- Run a shell (`terminal` toolset is off)
- Install Python packages (no shell = no `pip install`)
- Spawn subagents (`delegation` is off)
- Schedule tasks (`cronjob` is off)
- Edit `~/.hermes/SOUL.md` or `~/.hermes/config.yaml` (chmod 444, hook denies)
- Reach the relay without a valid HMAC signature
- Reach the operator's internal services from the agent (URL denylist)
- Pivot from the agent to attack the user's host OS (no shell, sandboxed code execution)
- Exfiltrate data via the agent's web tools (URL denylist catches common exfil hosts)
- Get the operator to execute their submitted code (operator's `collector` profile has no auto-merge; reviews are manual)

### What could still go wrong (and mitigations)

- **The user could fork the bundle and remove the denylist.** Yes. The PoC's defense is "users trust the operator." The mitigation is: if a user forks, they're on their own, and their data no longer reaches your relay (different secret). You could later add a signed-manifest check (each user install verifies the denylist hash against your public key).
- **A prompt-injection could trick the user themselves into pasting a credential into a web form the agent renders.** Out of scope. The user's own browser, their own action.
- **Oracle could reclaim the always-free instance.** Mitigation: daily-ping cron writes a file every 24h, so the instance shows activity.
- **A zero-day in FastAPI, Pydantic, or the Python HTTP stack.** Out of scope for the PoC. Mitigation: keep the relay's deps pinned and minimal.

## File ownership (re-stated, per the hermes-profile-taxonomy rule)

| Path | Owned by | Notes |
|---|---|---|
| `~/.hermes/SOUL.md` | operator | read by ALL profiles as identity |
| `~/.hermes/config.yaml` | operator | global config |
| `~/.hermes/.env` | operator (or user) | API keys |
| `~/.hermes/skills/` | operator | global skill catalog |
| `~/.hermes/profiles/default/SOUL.md` | synthetic alias | doesn't exist; uses global |
| `~/.hermes/profiles/default/config.yaml` | synthetic alias | exists as overlay |
| `~/.hermes/profiles/collector/SOUL.md` | operator | quarantine role |
| `~/.hermes/profiles/collector/config.yaml` | operator | quarantine config |
| `~/.hermes/profiles/collector/quarantine/` | operator | submissions land here |
| `~/.hermes/profiles/<user_uuid>/*` | user | their install state |
| `hermes-dist/default-template/SOUL.md` | operator | distribution bundle |
| `hermes-dist/default-template/config.yaml` | operator | distribution bundle |
| `hermes-dist/default-template/hooks/*` | operator | distribution bundle |
| `hermes-dist/default-template/security/*` | operator | distribution bundle |
| `hermes-dist/relay/*` | operator | relay source |
