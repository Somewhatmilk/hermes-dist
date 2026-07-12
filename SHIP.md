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

**Skill total:** 4 auto-load + 13 opt-in = 17 universal skills (~550 KB opt-in surface, 0 KB additional system-prompt cost vs v0.4.0). mnemosyne-memory bumped from 33 KB → 36 KB with a new "Mental Model" section at the top (read-first before the API surface).

**v0.4.2 (this commit):** added `cross-session-todo-handoff` opt-in skill (10 KB) — addresses the "I run multiple parallel sessions and the next session doesn't know what the previous one was doing" failure mode. Pattern: write a `work.in_progress` canonical Mnemosyne slot + a high-importance dated `mnemosyne_remember` at session end; read both at session start. Designed to be sleep-resistant (importance ≥0.85 + `valid_until` ~1 month).

**v0.4.3 (this commit):** added `mnemosyne-tuning` opt-in skill (9 KB) — addresses the secondary failure mode where Mnemosyne recall drops high-importance recent facts in favor of mid-importance older facts. Pattern: per-call recall_weights (vec=0.4, fts=0.3, importance=0.3) instead of (0.5, 0.3, 0.2); env-var overrides for persistence; always combine high-importance + valid_until when writing handoffs. Also added a 5-line "session-start handoff ritual" section to the auto-load `routing` skill so the cross-session todo read happens automatically. Skill v1.1.0 corrects v1.0.0 speculation (Mnemosyne's recall_weights are env-var-or-per-call only, NOT in `~/.hermes/config.yaml` schema; `pinned=1` is the actual "do not consolidate" flag but isn't exposed via the wrapper).

**v0.4.4-cross-session (this commit):** ships `hermes-changelog.py` — a cross-session change-log writer that mirrors every logged change to BOTH (a) the user's Obsidian vault at `~/Desktop/Obsidian Vault/Hermes Engine/changes/<ISO>-<slug>.md` for human browsing and (b) the Mnemosyne shared-surface DB at `~/.hermes/mnemosyne/data/shared/mnemosyne.db` for agent recall. The shared-surface write was previously blocked because `shared_surface_read: false` by default; this commit also enables that flag in `~/.hermes/config.yaml` (operator-side, not in the dist repo). Usage:

```
python3 ~/.hermes/scripts/hermes-changelog.py --kind skill-shipped --slug my-skill --summary "..." --details "..."
python3 ~/.hermes/scripts/hermes-changelog.py --list   # recent changes
```

The script's Mnemosyne write tries the high-level wrapper first, falls back to direct SQLite INSERT to `working_memory` table (schema-verified). Other agents with `shared_surface_read: true` will see these writes in their next recall — this is the practical cross-session "synced brain" mechanism. v0.4.4 also ships a `kanban-changelog-reader.md` template at `default-template/templates/kanban-changelog-reader.md` so users can run a kanban worker that mirrors Mnemosyne writes back to Obsidian on a schedule (optional, opt-in).

**v0.4.5-skill-union (this commit):** 4 new opt-in skills promoted from the "other agent's" parallel-session work, + 2 universal-section extracts into existing shipped skills. All promoted after a triage report (`~/.hermes/sessions/2026-07-12-skill-triage-report.md`) that audited 20 of the other agent's recent skills against the universal-vs-operator boundary.

NEW opt-in skills:
- `prompt-interview-pattern` (10 KB, `productivity/`) — interview the user before writing, one question at a time. Complements shipped `socratic-prompting` (which is teaching; this is scope clarification).
- `session-continuity-advisor` (14 KB, `hermes/`) — when to /new, when to reload context, when to query prior sessions. Pairs with shipped `cross-session-todo-handoff` (decides WHAT carries across; this decides WHEN to switch).
- `addon-protocol` (13 KB, `meta/`) — threat-tiered sandbox + 7-step ADDON procedure. Pairs with shipped `skill-library-consolidator` (which surveys what exists; this governs the ACT of adding).
- `information-validation` (25 KB, `research/`) — cross-reference methodology, the `success: true` ≠ evidence discipline, the proactive-research-before-claiming rule. Highest-priority universal shipping — closes the "agent cited plausible-but-wrong number" failure mode.

MERGED into existing shipped skills (no new top-level skill, extracted universal sections only):
- `hermes-misbehavior-diagnosis/references/error-classification.md` (9 KB) — extracted "Pre-flight procedure + Error classification table + Pitfalls" from `hermes-llm-preflight`. The "classify error before retry" pattern extends misbehavior-diagnosis. The full `hermes-llm-preflight` (38 KB, operator-specific WSL2 / kanban / ollama sections) stays local.
- `skill-library-consolidator/references/refactor-procedure.md` (7 KB) — extracted "The Refactor Procedure" from `hermes-skill-refactor`. The 7-step procedure + 11-pitfall catalog is genuinely additive. The full `hermes-skill-refactor` (30 KB, operator-specific verification patterns) stays local.

KEPT LOCAL-ONLY (operator-specific, no shipping): `hermes-dispatch-gate`, `hermes-kanban-architecture`, `task-deferral-pattern`, `kanban-worker-lifecycle`, `camofox-persistent-browser`, `hermes-config-cli-gotchas`, `hermes-distribution-packaging`, `web-research-stack-2026-07-12`, `reddit-canon-sweep`, `hermes-llm-preflight`, `hermes-skill-refactor`, `self-contained-spa-html`. Reason: most reference operator-specific paths, joandrew.com.sg workflow, or local Docker stack (camofox :9377, SearXNG :8888, firecrawl :3002, crawl4ai, browser-use) that other users won't have.

DEFERRED for future v0.4.6+ (after trimming to ≤15 KB):
- `deep-research-methodology` (38 KB) — universal 5-layer framework but with domain-specific examples (kbd/Steam); trim before shipping
- `verify-before-claim-hardware` (40 KB) — universal "verify before claiming" rule but with hardware-specific recipes (nvidia-smi, etc.); trim before shipping

NO new auto-load skills (4 auto-load unchanged). System-prompt cost still ~104 KB. Total opt-in surface: 18 skills (~510 KB), up from 14 in v0.4.3.

**v0.4.6-subagent-resume (this commit):** ships `subagent-with-resume.py` — a resumable subagent dispatch wrapper that solves the "subagent gets blocked/dropped/503/rate-limited and loses all in-flight state" failure mode (user canon 2026-07-10). Pattern: deterministic subagent UUID from `hash(goal + context_digest)` so retries use the SAME scratchpad namespace; subagent writes progress checkpoints to `mnemosyne_scratchpad_write("subagent/<uid>/...", ...)` before each expensive tool call; if subagent fails (timeout, non-zero rc, rate-limit), the wrapper re-dispatches with prior scratchpad state injected into context; up to N retries. Also ships the `subagent-resumability` opt-in skill documenting the pattern + the discipline (sparse scratchpad writes, "before risky call checkpoint FIRST", "approaching budget write final-state"). No new auto-load skill (system-prompt cost stays at ~104 KB). Total opt-in: 19 skills (~520 KB).

The pattern generalizes to kanban workers (`kanban-<task-id>` namespace) and profile-routed agents (`profile-<profile>-<session-id>` namespace) — the discipline (exact-state checkpoints before expensive ops) is the same; only the UID scheme differs. README-level usage:

```
python3 ~/.hermes/scripts/subagent-with-resume.py \
  --goal "Research X" \
  --context "background context" \
  --max-retries 5 \
  --timeout-s 900
```

Logs every attempt to `~/.hermes/logs/subagent-resume.log`. Cost: ~250 tokens overhead per subagent run (~5 scratchpad writes × 50 tokens each). Savings on retry: full subagent re-run avoided.

**v0.4.7-installers + v0.4.7-fix (commits `60e3385` + `91b49cc`):** bring
Linux/macOS installers to v0.4.0/v0.4.1 parity with Windows (systemd user
timer + launchd plist running the daily-update-check at 09:00, with
notify-send / osascript toast on new tag). Then fix the
subagent-with-resume scratchpad layer: `_scratchpad_write/query` now
uses direct SQLite against the agent's real DB instead of shelling
out to a non-existent CLI subcommand. End-to-end smoke verified: real
`hermes chat` via wrapper returned `V047_VERIFIED` correctly; scratchpad
state persisted across runs (772-word count of README.md confirmed
correct against `wc -w`).

**v0.4.8-trim+index+mcps (this commit):** four new artifacts.

1. **Trimmed `deep-research-methodology`** from 38 KB → 15 KB. Kept
   the 5-layer framework (breadth / depth / time / cross-validation /
   meta) + 10 universal pitfalls. Removed operator-specific sections
   (Morimens case, a11y virtualization, aesthetic recs).

2. **Trimmed `verify-before-claim-hardware`** from 40 KB → 16 KB. Kept
   the rule + the 5-step reflex + Windows diagnostic commands + the
   12 universal anti-patterns. Removed operator-specific hardware
   (ZOTAC, Acer PD, WDDM, mmproj, VideoOutputTechnology cheat-sheet).

3. **`default-template/SKILLS.md`** — 10 KB index of all 25 SKILL.md
   files in dist repo, grouped by auto-load vs opt-in, with
   "indexes by purpose" (research work, hermes internals, shell
   scripting, etc.). One-stop reference for which skills ship.

4. **`default-template/mcps/`** — 3 starter compose-yamls (filesystem
   MCP, browser-worker MCP, SearXNG) + readme.md explaining the
   Tailscale-bind model, authentication, and update workflow.

NO new auto-load skills. System-prompt cost still ~104 KB. Both
trimmed skills ship as opt-in; users who need the operator-specific
content can read the upstream versions at `~/.hermes/skills/...`.

**Auxiliary client fallback chain observation (NOT a code change —
flagging for review):** the EXPLICIT-provider fallback path in
`hermes-agent/agent/auxiliary_client.py` calls `_try_main_agent_model_fallback`
as step 2, but the canonical order (per the code comment) places
"main agent model safety net" at step 4 — AFTER `_try_payment_fallback`
which the EXPLICIT path skips entirely. This is a coverage gap, not
an inversion per se. The risk of changing fallback order is that a
user relying on the current behavior breaks; recommend a config-gated
fix once user confirms. Documented here for the v0.4.8 commit but
NO code change shipped.


**v0.4.9-subagent-namespace-variants (this commit):** two new opt-in skills
that extend the v0.4.6 subagent-resumability discipline to the kanban
and profile-routed surfaces. Per the v0.4.6 canon: "the discipline is
the same, only the UID scheme differs." So no new wrapper scripts —
the v0.4.6 `subagent-with-resume.py` works as-is, you just supply a
different `--uid`.

NEW opt-in skills:
- `kanban-worker-resumability` (6 KB, `meta/`) — UID scheme:
  `kanban-<task-id>`. Complements the existing kanban DB layer with
  in-session exact-state checkpoints.
- `profile-agent-resumability` (8 KB, `meta/`) — UID scheme:
  `profile-<profile-name>-<session-id>`. Complements the routing
  auto-load skill with per-profile-session scratchpad checkpoints.

ISSUE FILED (not in dist repo; at `~/.hermes/issues/`):
The auxiliary client fallback order in
`hermes-agent/agent/auxiliary_client.py:6908-6935` has a
comment/code inconsistency — the comment documents 4 fallback steps
but the EXPLICIT path skips step 3. Documented for upstream review
at `~/.hermes/issues/2026-07-12-aux-fallback-order.md`. My
recommendation: treat the code as correct (Interpretation B), fix the
comment. **No code change shipped** — the risk of changing fallback
order silently is too high without operator sign-off.

NO new auto-load skills. System-prompt cost still ~104 KB. Total
opt-in: 20 SKILL.md files (4 auto + 20 opt-in), ~537 KB.



**v0.4.10-aux-fallback-fix (commit `bdfbba2`):** ships
`scripts/aux-fallback-fix.py` — config-gated runtime monkey-patch
that adds step 3 (built-in discovery chain) to the EXPLICIT-provider
fallback path. Default OFF preserves historical behavior. Opt-in via
`auxiliary.<task>.allow_discovery_fallback: true`.

ALSO VERIFIED: the v0.4.6 subagent-with-resume.py failure-recovery
path. Killed PID 31868 at +8s, scratchpad goal entry survived, re-run
with same UID returned "(resuming — prior progress found in
scratchpad)". The previously-unproven claim is now evidence-backed.

**v0.4.11-smoke-consolidation (commit `94f1e6c`):** ships 3 smoke
scripts implementing the user-canonical pattern:
- `smoke-leaf.py` — `smoke-leaf-{n}` session, 5 canonical queries
- `smoke-kanban.py` — synthetic `smoke-kanban-{ts}-{rand}` task, 3 queries
- `smoke-profile.py` — per-profile session, 3 queries × 8 profiles

REPLACES the per-verifier `reply with exactly X` decoration pattern
that spawned 13 hermes chat sessions across v0.4.6 → v0.4.10 (all
deleted via `hermes sessions delete` before this commit).

NEW canonical verifier: `verification/hermes-verify-v0411.py`
(schema + git + scratchpad queries only; no hermes chat spawns).

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
