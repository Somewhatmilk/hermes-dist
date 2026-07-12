# Hermes Dist — Ship Runbook (v0.3.0)

**Concrete sequence of commands to go from "code on your laptop" to "users on your Tailscale network can install it, and the operator can push updates."**

Estimated total time: **20 minutes** (15 min of hands-on-keyboard for Tailscale auth + first deploy, 5 min of waiting for Docker to build).

The relay runs on **this PC** (the operator's box) and is reached over **Tailscale** at `https://<host>.tail.ts.net:9119` or directly at `https://100.106.125.105:9119`. No public IP, no SSH bastion — Tailscale gives a stable 100.x.x.x address and encrypts traffic over WireGuard through DERP relays.

**v0.3.0 update (this commit):** cross-OS installers (Linux/macOS/Windows), per-OS path detection, Tailscale CGNAT 100.x.x.x denied in security/denylist.yaml, push-update heartbeat (`POST /api/v1/profile-bundle` + 60s client poll), profile-bundle replaces operator-pull on every config change.

**v0.4.0 design:** heartbeat replaced with **user-initiated `hermes update-dist`** (no auto-apply). On hermes launch / daily scheduled task, the installer checks `https://api.github.com/repos/Somewhatmilk/hermes-dist/releases/latest`. If newer than `~/.hermes/profiles/<uuid>/.hermes-dist-version`, a toast prompts the user: *"hermes-dist v0.3.1 available. Run `hermes update-dist` to review and apply."* User runs `hermes update-dist` to see the diff and approve.

**v0.4.1-skills (this commit):** extended the opt-in skill catalog. **0 new auto-load skills** (system-prompt cost stays at ~104 KB), **6 new opt-in skills** (~152 KB additional surface, only loads when user explicitly opts in):
- `web-interaction` (12 KB, SKILL.md only — references pulled on demand) — web scraping/automation patterns
- `background-process-lifecycle` (36 KB) — daemon/watcher lifecycle, session_id discipline, notify-vs-watch decision
- `cross-platform-bash-scripting` (84 KB) — OSTYPE-aware bash, cron/launchd/systemd/Task-Scheduler dispatch, MSYS path-bridge
- `prompt-direction-format-examples` (6 KB, NEW) — the 5-step prompt ladder
- `diagnose-root-cause` (5 KB, NEW) — patch the cause, not the symptom
- `socratic-prompting` (6 KB, NEW) — 3-questions pattern for strategic work

**Skill total:** 4 auto-load + 12 opt-in = 16 universal skills (~540 KB opt-in surface, 0 KB additional system-prompt cost vs v0.4.0). mnemosyne-memory bumped from 33 KB → 36 KB with a new "Mental Model" section at the top (read-first before the API surface).

**Verified-live state (2026-07-11, this commit):**
- Relay at v0.2.2 (commit `3ca9857`) with v0.3.0 installer updates (commit `b2c8a86`)
- `--workers 1` (PoC, in-process nonce store)
- `apscheduler` timezone = `UTC` (slim image rejects `local`)
- 100.x.x.x in denylist (Tailscale CGNAT isolation)
- 16/16 self-test pass + dogfood install: 3 audit events shipped to relay with HTTP 200, all HMAC-verified

---

## Stage 0: Verify everything works locally (5 min)

```bash
cd ~/hermes-dist
git log --oneline | head -3
# Should show:
#   b2c8a86 v0.3.0-patch1: .onboard.sh substitutes <<WORKING_DIR>> from env
#   d700c37 v0.3.0: cross-OS installers (Linux/macOS/Windows) + portable paths
#   3ca9857 v0.2.2: deny 100.x.x.x in URL + script_strings (Tailscale CGNAT isolation)

# Re-run the local relay dry-test
cd relay
bash tests/dry-run.sh
```

Expected: 4 HMAC cases pass + T9 flood + T3 profile-bundle test. The script auto-cleans the container.

If any test fails, **stop**. Don't deploy a broken relay.

---

## Stage 1: Push to GitHub (5 min, ALREADY DONE for this user)

```bash
gh auth status  # confirm login
gh repo create Somewhatmilk/hermes-dist --public --source=. --remote=origin --description "Hermes Dist: Tailscale-relay + HMAC-signed audit + cross-OS installers" --push
git push origin master --follow-tags
```

`Somewhatmilk/hermes-dist` is **already public at v0.3.0** (as of 2026-07-11). If you're starting fresh:

```bash
# After repo creation:
git push origin master --follow-tags
# v0.3.0 should appear under Releases
```

---

## Stage 2: Tailscale on this PC (2 min, ALREADY UP for this user)

Tailscale is at `C:\Users\<user>\AppData\Local\Tailscale\` and **already up** as of 2026-07-11 (3 devices on the tailnet, this PC is `notion` at `100.106.125.105`). To re-verify:

```bash
tailscale status
# Should show: 100.106.125.105  notion  Somewhatmilk@  windows  -
```

If you need to re-auth (e.g. on a fresh install):
```bash
tailscale up        # browser SSO flow
tailscale status    # confirm
ping notion.tail.ts.net  # should respond from 100.x.x.x
```

**Wake-from-sleep recipe** (zero-click after enabling auto-start):
1. Tailscale tray → Preferences → ☑ Run Tailscale when computer starts
2. Docker Desktop → Settings → General → ☑ Start Docker Desktop when you sign in
3. `docker run` with `--restart unless-stopped` (already in Stage 3)
4. ~45 sec after PC wake, `curl http://notion.tail.ts.net:9119/api/v1/healthz` returns 200

---

## Stage 3: Deploy the relay on this PC (3 min — VERIFIED LIVE 2026-07-11)

### 3a. Generate the operator token

```bash
cd ~/hermes-dist/relay
export OPERATOR_TOKEN=$(openssl rand -hex 32)
echo "$OPERATOR_TOKEN" > .operator-token-test
chmod 600 .operator-token-test
echo "Token: $(cut -c1-12 .operator-token-test)***"
```

**Save this token.** It's the only way to query events.

### 3b. Build + start the container

```bash
docker build --no-cache -t hermes-relay:latest .
# (--no-cache defeats the Docker layer-cache pitfall that masks host-side edits)

docker run -d --name hermes-relay \
  --restart unless-stopped \
  -p 127.0.0.1:9119:9119 \
  -p 100.106.125.105:9119:9119 \
  -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
  -v hermes-relay-data:/var/lib/hermes-relay \
  hermes-relay:latest
```

**The Tailscale IP bind (`-p 100.106.125.105:9119:9119`) is the load-bearing line for cross-device reachability.** Without it, the relay is only on `127.0.0.1` and other tailnet devices can't reach it. If your Tailscale IP differs, substitute the correct one.

**`--workers 1` is hardcoded in the Dockerfile CMD** (committed in v0.2.1). The PoC in-process nonce store does NOT share state across workers — running with `--workers 2` silently breaks replay-defense. Production fix: Redis-backed nonce store (out of scope for PoC).

### 3c. Verify

```bash
sleep 5
docker ps --filter name=hermes-relay --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
# Should say: Up X seconds (healthy) | 127.0.0.1:9119->9119/tcp, 100.106.125.105:9119->9119/tcp

curl -s http://127.0.0.1:9119/api/v1/healthz
# {"ok":true,"version":"hermes-relay-0.1.0",...}

curl -s http://100.106.125.105:9119/api/v1/healthz
# same JSON — Tailscale routes to the container
```

If `healthz` returns empty or the container is in `Restarting` state, check the logs:

```bash
docker logs hermes-relay --tail 30
# Common issue: pytz.exceptions.UnknownTimeZoneError: 'local'
# Fix: relay/app/main.py line ~218 should say timezone="UTC" (committed in v0.2.0+)
# If you see this, you need to update the code: git pull && docker build --no-cache
```

### 3d. Propagate the operator token to your operator profile

```bash
OP_PROFILE="$HOME/.hermes/profiles/collector"
mkdir -p "$OP_PROFILE"
cp ~/hermes-dist/relay/.operator-token-test "$OP_PROFILE/.operator-token"
chmod 600 "$OP_PROFILE/.operator-token"
```

Verify with the operator-auth query:
```bash
curl -sS -H "X-Operator-Token: $(cat $OP_PROFILE/.operator-token)" \
  http://127.0.0.1:9119/api/v1/users | python3 -m json.tool
# Should return: {"ok":true,"count":0,"users":[]}
```

---

## Stage 4: Dogfood install (10 min — VERIFIED LIVE 2026-07-11)

Before shipping to real users, install a test instance. **Do this in a sandbox dir, NOT your real `~/.hermes`.** The pattern:

```bash
mkdir ~/hermes-dist-test
cd ~/hermes-dist-test

# Copy the cross-OS installer (whichever matches your test host)
cp ~/hermes-dist/install-windows.ps1 .    # Windows test
# or
cp ~/hermes-dist/install-linux.sh .       # Linux test
# or
cp ~/hermes-dist/install-macos.sh .       # macOS test

# Run with the local repo as source (faster than GitHub clone)
$env:HERMES_DIST_REPO = "C:\Users\somew\hermes-dist"
$env:HERMES_RELAY_URL = "http://100.106.125.105:9119"

powershell -ExecutionPolicy Bypass -File ".\install-windows.ps1"
```

The installer:
1. Verifies Python + Git + Docker
2. Installs Hermes (or uses existing)
3. Reads the dist repo (skipping `git clone` if local)
4. Runs `.onboard.sh`: generates UUID, prompts opt-in, wires the 3 hooks, registers with relay
5. Sets up scheduler: Windows Task Scheduler / launchd plist / systemd user timer

**Test the security model** with the bundled CLI (this is the v0.3.0 test):
```bash
# Self-test: 16-case allowed-vs-denied matrix
python bin/hermes-dist-test.py self-test
# 16/16 pass expected

# Chat (registers on relay, ships HMAC-signed audit events)
python bin/hermes-dist-test.py chat "Hello relay"
# [registered] uuid=... -> got hmac_secret len=64
# [profile=default] hook=allow | relay HTTP 200: {"ok":true,"event_id":1,...}

# Quarantine escalation
python bin/hermes-dist-test.py chat "running an admin command" --quarantine "ESCALATE TO QUARANTINE"
# Switched to quarantine profile.

# Audit log (local + relay)
RELAY_OPERATOR_TOKEN="$(cat ~/hermes-dist/relay/.operator-token-test)" \
  python bin/hermes-dist-test.py audit --last 10
```

Verify the security model (try the LLM-attacker cases — they all fail):
- ✗ `chat "Try to read ~/.ssh/id_rsa"` → hook denies, audit captures the attempt
- ✗ `chat "curl http://100.99.116.121:22"` → hook denies (Tailscale CGNAT in denylist)
- ✗ `chat "rm -rf /"` → hook denies (commands.deny: rm), audit logs

---

## Stage 5: Cut a release (push to GitHub)

```bash
cd ~/hermes-dist
git tag v0.X.Y
git push origin v0.X.Y
```

Users running `hermes update` (operator-side) get the new version, AND the operator can `POST /api/v1/profile-bundle` to push profile changes to all users in <60s via the heartbeat.

---

## Stage 6: Invite real users (2 min each)

For each user, send them:
1. **A Tailscale invite** — Tailscale → Access Controls → invite, OR share a node from your account
2. **One command**, depending on their OS:

| OS | Command |
|---|---|
| **Windows** | `irm https://raw.githubusercontent.com/Somewhatmilk/hermes-dist/v0.3.0/install-windows.ps1 \| iex` |
| **macOS** | `curl -fsSL https://raw.githubusercontent.com/Somewhatmilk/hermes-dist/v0.3.0/install-macos.sh \| bash` |
| **Linux** | `curl -fsSL https://raw.githubusercontent.com/Somewhatmilk/hermes-dist/v0.3.0/install-linux.sh \| bash` |

The installer:
- Detects OS, sets HERMES_HOME + WORKING_DIR correctly per-OS
- Installs hermes + reads the dist repo
- Prompts opt-in
- Sets up per-OS scheduler (Windows Task Scheduler / launchd plist / systemd user timer)
- Heartbeat starts polling your relay every 60s

**Without the tailnet invite, users cannot reach `100.106.125.105:9119`.** That's the point of Tailscale — your ISP IP never appears in their config.

If a user needs off-tailnet access, enable Tailscale Funnel (NOT recommended by default):
```bash
tailscale serve --bg --https=9119 http://localhost:9119
tailscale funnel --bg --https=9119 http://localhost:9119
```

---

## Stage 7: Push updates to users (the seamless-update answer)

When you change SOUL.md, default-template/config.yaml, or the denylist:

```bash
cd ~/hermes-dist
# 1. Edit + commit + tag
git add . && git commit -m "v0.3.1: tighten denylist"
git tag v0.3.1 && git push origin v0.3.1

# 2. Push the new profile bundle to the relay
curl -X POST http://127.0.0.1:9119/api/v1/profile-bundle \
  -H "X-Operator-Token: $(cat relay/.operator-token-test)" \
  -H "Content-Type: application/json" \
  -d "{
    \"soul_md\": \"$(cat default-template/SOUL.md | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')\",
    \"config_yaml\": \"$(cat default-template/config.yaml | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')\",
    \"toolsets_json\": \"[\"file\",\"web\",\"docker\",\"webscraping\"]\",
    \"version\": \"v0.3.1-2026-07-11\",
    \"released_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }"

# 3. Users' heartbeat.sh picks it up within 60s
# 4. Users see "new version from operator" toast on next launch
```

The user doesn't run `hermes update` themselves. They get your push within ~60s. The system prompt, toolset list, and security policy update without restart.

---

## Stage 8: Daily operations (1 min/day)

```bash
# 1. Verify relay is still running
docker ps --filter name=hermes-relay --format '{{.Status}}'
# Up X hours (healthy)

# 2. Query new events
curl -sS -H "X-Operator-Token: $(cat ~/.hermes/profiles/collector/.operator-token)" \
  http://100.106.125.105:9119/api/v1/events?limit=20 | python3 -m json.tool | head -50

# 3. Review
hermes-distribution pull       # downloads events into ~/.hermes/profiles/collector/quarantine/
hermes-distribution list
hermes-distribution review memories
hermes-distribution review skills
hermes-distribution review scripts

# 4. Approve / reject
hermes-distribution approve ~/.hermes/profiles/collector/quarantine/memories/<file>.json
hermes-distribution reject ~/.hermes/profiles/collector/quarantine/skills/flagged/<file>.json "reason"
```

---

## Common issues + recovery

| Symptom | Root cause | Fix |
|---|---|---|
| `pytz.exceptions.UnknownTimeZoneError: 'local'` | apscheduler can't resolve `local` on slim image | Use `timezone="UTC"` (already committed in v0.2.0+) |
| Container in `Restarting` state, healthz empty | Usually apscheduler init or stale DB | `docker logs hermes-relay --tail 50`; if it's a WAL lock, `docker stop hermes-relay && docker rm hermes-relay` then re-run |
| Replay test returns 200 instead of 401 | `--workers 2` and nonce store singleton doesn't share | Dockerfile CMD has `--workers 1`; rebuild with `docker build --no-cache` |
| Tailscale can't reach the relay | `-p 100.106.125.105:9119:9119` not in your `docker run` line | Re-create the container with the Tailscale IP bind |
| User's hermes-dist CLI shows "relay HTTP 401 Invalid signature" | Per-user secret from registration not yet stored in state | Re-run `python bin/hermes-dist-test.py chat` to re-register; state persists in `logs/state.json` |
| User can't reach relay URL | User not on the tailnet | Send Tailscale invite from your account |

---

## Time check (verified 2026-07-11)

- Stage 0: 5 min (you) — verify
- Stage 1: 0 min (already done — v0.3.0 is pushed)
- Stage 2: 0 min (already up — Tailscale running, 3 devices)
- Stage 3: 3 min (token + docker run + verify) — VERIFIED DONE
- Stage 4: 10 min (sandbox install + tests) — VERIFIED DONE (16/16 self-test + 3 audit events)
- Stage 5: 0 min (already tagged v0.3.0)
- Stage 6: 2 min per user (when you have a real user)
- Stage 7: 30 sec (push update flow)
- **Total: 20 min for end-to-end ship** — VERIFIED

After that, you're in maintenance mode (1 min/day for review, 30 sec per push update).
