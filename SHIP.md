# Hermes Dist — Ship Runbook

**This is the concrete sequence of commands to go from "code on your laptop" to "users on your Tailscale network can install it".**

Estimated total time: **20 minutes** (15 min of hands-on-keyboard for Tailscale auth + first deploy, 5 min of waiting for Docker to build).

The relay runs on **this PC** (the operator's box) and is reached over **Tailscale MagicDNS** at `https://<host>.tail.ts.net:9119`. No public IP, no SSH bastion — Tailscale gives you a stable 100.x.x.x address and encrypts traffic over WireGuard through DERP relays. When you eventually move the relay to a NAS or VPS, only the MagicDNS name changes; users' `gateway_config.json` stays the same. See the `hermes-distribution-packaging` skill → **Migration PC → NAS via DNS entrypoint**.

---

## Stage 0: Verify everything works locally (5 min)

```bash
cd ~/hermes-dist
git log --oneline | head -3
# Should show: v0.1.0: hermes-dist PoC bundle

# Re-run the local relay dry-test
cd relay
bash tests/dry-run.sh
```

Expected: 4 test cases pass (event accepted, replay rejected, bad signature rejected, operator query works). The script auto-cleans the container.

The dry-run also writes the freshly-generated `OPERATOR_TOKEN` to `relay/.operator-token-test` (chmod 600 by convention; you do this manually in Stage 3 below). **Don't lose this token** — it's the only way to query events.

If any test fails, **stop**. Don't deploy a broken relay.

---

## Stage 1: Push to GitHub (5 min)

You need: a GitHub account. The hermes-cli is already installed if you have `gh` (you don't yet — install first).

### Install `gh` CLI

```bash
# Windows (you're on Windows)
winget install --id GitHub.cli -e

# macOS
brew install gh

# Linux
sudo apt install gh   # or equivalent
```

### Authenticate

```bash
gh auth login
# → GitHub.com
# → HTTPS
# → Authenticate with browser (opens localhost callback)
# → Confirm the OAuth token works
```

Verify:
```bash
gh auth status
```

### Create the public repo and push

```bash
cd ~/hermes-dist
gh repo create you/hermes-dist --public --source=. --remote=origin --description "Hermes Dist PoC bundle: restricted default profile + HMAC relay" --push
```

Replace `you` with your actual GitHub username.

Verify:
```bash
gh repo view you/hermes-dist --web
```

You should see the README in your browser.

---

## Stage 2: Bring Tailscale up on this PC (2 min, then ~45s per wake)

The relay lives on THIS box. Tailscale is what makes it reachable without exposing your ISP-assigned IP. Tailscale is already installed at `%LOCALAPPDATA%\Tailscale\` — you just need to authenticate and enable MagicDNS.

### 2a. Start the Tailscale service and authenticate

Open the Tailscale app from the Start menu (or run `tailscale.exe` from `C:\Users\somew\AppData\Local\Tailscale\`). The tray icon will prompt you to sign in.

```bash
# Equivalent CLI path (same login URL appears in browser)
tailscale up
```

Follow the browser flow:
1. Sign in with the account that owns your tailnet (Google / Microsoft / GitHub / etc.)
2. Approve this device
3. Re-run `tailscale up` if you want a stable MagicDNS name; the default is the hostname of this PC (e.g. `somew-pc`).

### 2b. Verify MagicDNS

```bash
tailscale status
# → 100.x.x.x   somew-pc   <user>@   windows   ...
tailscale ip -4
# → 100.x.x.x

# MagicDNS name resolves to your tailnet IP
ping <host>.tail.ts.net
# Should respond from 100.x.x.x — NOT your ISP IP
```

`%LOCALAPPDATA%\Tailscale\tailscale-status.json` will show the registered node. The `<host>` segment comes from your Windows hostname — rename the PC before `tailscale up` if you want a different name. Underscores are not allowed; hyphens are.

### 2c. Enable "run at startup" and Docker auto-start

In the Tailscale tray menu → **Preferences**:
- ☑ **Run Tailscale when computer starts**

In Docker Desktop → **Settings → General**:
- ☑ **Start Docker Desktop when you sign in**

After this, the wake-from-sleep recipe from the skill applies verbatim:

1. Power on PC. Windows boots.
2. Docker Desktop starts automatically.
3. Tailscale starts automatically.
4. Docker containers restart automatically (compose file: `restart: unless-stopped`).
5. Wait ~45 sec. `curl https://<host>.tail.ts.net:9119/api/v1/healthz` returns 200. Users can reach the relay.

Single on-call assumption: Docker Desktop service comes up before users try to hit the gateway. The 45-sec window on every PC boot is acceptable for ≤5 users.

### 2d. If/when you graduate PC → VPS/NAS

See the skill's **Migration PC → NAS via DNS entrypoint** recipe. Short version: bind the gateway at the DNS layer (CNAME `relay.<your-domain>` → `<host>.tail.ts.net`), provision the new host, flip the CNAME, revoke old HMAC keys. Users never reconfigure anything.

---

## Stage 3: Deploy the relay on this PC + propagate the operator token (5 min, mostly automated)

The relay is a FastAPI app in a Docker container. It binds to `127.0.0.1:9119` and is reached over Tailscale via MagicDNS. Tailscale's DERP relay handles the WireGuard transport; the relay's own HMAC layer handles authentication.

### 3a. Build the image

```bash
cd ~/hermes-dist/relay
docker build -t hermes-relay:latest .
```

### 3b. Generate the OPERATOR_TOKEN (if you skipped Stage 0)

```bash
# Fresh, cryptographically random, 64 hex chars
export OPERATOR_TOKEN=$(openssl rand -hex 32)
echo "$OPERATOR_TOKEN" > .operator-token-test
chmod 600 .operator-token-test
```

This is the same token the dry-run writes in Stage 0. **Save it now** — it's the only way to query events.

### 3c. Start the container

```bash
docker run -d --name hermes-relay \
  --restart unless-stopped \
  -p 127.0.0.1:9119:9119 \
  -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
  -v hermes-relay-data:/var/lib/hermes-relay \
  hermes-relay:latest
```

Verify it's up on localhost:

```bash
curl -s http://127.0.0.1:9119/api/v1/healthz
# → {"ok": true, "version": "hermes-relay-0.1.0", ...}
```

### 3d. Verify the relay is reachable over Tailscale

From this same PC, or any other device on your tailnet:

```bash
curl -s https://<host>.tail.ts.net:9119/api/v1/healthz
```

Substitute `<host>` with the MagicDNS name you saw in `tailscale status` (e.g. `somew-pc.tail.ts.net`). Expected:

```json
{
  "ok": true,
  "version": "hermes-relay-0.1.0",
  "uptime_seconds": 12.4,
  "db_size_mb": 0.04,
  "user_count": 0,
  "event_count": 0
}
```

If you get a connection error, check:
- Tailscale is up on this PC: `tailscale status` (your node should be `connected`)
- The container is running: `docker ps` (look for `hermes-relay`)
- The Tailscale service is allowing loopback connections: `tailscale ping <host>.tail.ts.net` from the same PC

### 3e. Propagate the operator token to the operator's hermes profile

The relay is now live, but the operator CLI (`hermes-distribution pull`, `hermes-distribution list`, etc.) needs the token at a known path. Wire it once now:

```bash
# Pick the path your hermes config uses (PowerShell-native path on Windows)
$opProfile = "$env:USERPROFILE\.hermes\profiles\collector"
New-Item -ItemType Directory -Force -Path $opProfile | Out-Null

# Copy the token from where dry-run.sh wrote it
Copy-Item .\relay\.operator-token-test "$opProfile\.operator-token" -Force

# Lock it down — this is the only way to query events
icacls "$opProfile\.operator-token" /inheritance:r /grant:r "$env:USERNAME:(R,W)" | Out-Null
```

Equivalent bash (Git Bash on Windows):
```bash
OP_PROFILE="$HOME/.hermes/profiles/collector"
mkdir -p "$OP_PROFILE"
cp relay/.operator-token-test "$OP_PROFILE/.operator-token"
chmod 600 "$OP_PROFILE/.operator-token"
```

Verify:
```bash
curl -sS -H "X-Operator-Token: $(cat ~/.hermes/profiles/collector/.operator-token)" \
  https://<host>.tail.ts.net:9119/api/v1/healthz
# → 200 OK with the same JSON
```

If you regenerate the token later (e.g. you redeploy and want to rotate), repeat step 3b + 3e. The token is the only thing that authorises operator-side reads; loss of this file means you must re-issue + re-distribute.

---

## Stage 4: Self-install test (5 min)

Before shipping to real users, install a test instance on YOUR OWN machine in a test directory to verify the end-to-end flow.

```bash
# In a test directory, NOT your real ~/.hermes
mkdir ~/hermes-dist-test
cd ~/hermes-dist-test

# Copy the installer
cp ~/hermes-dist/install-windows.ps1 .

# Run it
.\install-windows.ps1 -RelayUrl "https://<host>.tail.ts.net:9119" -DistRepo "https://github.com/you/hermes-dist"
```

This will:
1. Verify Python + Git + Docker
2. Install Hermes if not present
3. Clone the dist repo
4. Run `.onboard.sh` (UUID gen, opt-in prompt, hooks wiring)
5. Start the tinysearch Docker container
6. Register the Windows Task Scheduler daily-update job

**When prompted "Opt in to data forwarding?", type `y` and press Enter.**

Test the agent:
```bash
hermes -p <your-uuid> chat
# Try: "Write a Python script to ~/Documents/test.py that prints 'hello'"
# Try: "Open https://example.com and tell me the title"
# Try: "Read ~/.hermes/SOUL.md" (should be denied)
# Try: "Run ls in the terminal" (should be denied)
# Exit: /exit
```

Verify the audit log captured everything:
```bash
cat ~/.hermes/audit.log
# Should show every tool call with timestamps
```

Verify the data reached the relay:
```bash
# As the operator (you)
hermes-distribution pull
hermes-distribution list
hermes-distribution review memories
```

You should see the test event in `~/.hermes/profiles/collector/quarantine/memories/`.

---

## Stage 5: Cut a release (so users see "v0.1.0 available")

```bash
cd ~/hermes-dist
git tag v0.1.0   # already tagged, but re-tag if you made changes
git push origin v0.1.0
```

Users running `hermes update` will see v0.1.0 as the current release.

---

## Stage 6: Invite a real user (5 min)

For each user, send them:
- The installer file (`install-windows.ps1` or `install-unix.sh`)
- The relay URL: `https://<host>.tail.ts.net:9119` (the same one you verified in Stage 3d)
- The dist repo URL (`https://github.com/you/hermes-dist`)
- An invite to your tailnet (Tailscale → Access Controls → invite, OR they install Tailscale and you share the node)

Without the tailnet invite, the user cannot reach `<host>.tail.ts.net` — that's the point of Tailscale (your ISP IP never appears in their config).

The instructions to give them:
```powershell
# Windows (PowerShell)
.\install-windows.ps1 -RelayUrl "https://<host>.tail.ts.net:9119" -DistRepo "https://github.com/you/hermes-dist"
```

```bash
# Mac/Linux
curl -O https://raw.githubusercontent.com/you/hermes-dist/main/install-unix.sh
chmod +x install-unix.sh
./install-unix.sh https://github.com/you/hermes-dist https://<host>.tail.ts.net:9119
```

They decide whether to opt in to data forwarding. Default: **opt-out** (no data leaves their box).

If you ever want a user on the **public internet** (not on your tailnet), enable Tailscale Funnel for port 9119:
```bash
tailscale serve --bg --https=9119 http://localhost:9119
tailscale funnel --bg --https=9119 http://localhost:9119
```

This routes their traffic through Tailscale's DERP relays — your ISP IP is still hidden. Only enable Funnel for users you explicitly opt in; the default is tailnet-only (safer).

---

## Stage 7: Daily operations on this box (5 min/day)

Everything is local now. No SSH, no remote bastion.

```bash
# 1. Pull new events from relay (which is on THIS box)
hermes-distribution pull

# 2. See what's pending review
hermes-distribution list

# 3. Review anything interesting
hermes-distribution review scripts
hermes-distribution review skills
hermes-distribution review memories

# 4. Approve / reject
hermes-distribution approve ~/.hermes/profiles/collector/quarantine/skills/clean/<file>.json
hermes-distribution reject ~/.hermes/profiles/collector/quarantine/skills/flagged/<file>.json "credential-theft attempt"

# 5. Check relay health (and verify it survived any reboots)
docker ps --filter name=hermes-relay --format '{{.Status}}'
tailscale status
curl -s https://<host>.tail.ts.net:9119/api/v1/healthz
```

### Common operational notes

- **PC sleep / wake**: ~45 sec for Docker + Tailscale to handshake on wake. Users see a brief timeout; the agent's next request retries. If they complain, see the skill's "Wake-from-sleep recipe" for zero-click setup verification.
- **Tailscale logged out**: re-auth in the tray. The relay keeps running on `127.0.0.1:9119` and is still reachable locally, but `<host>.tail.ts.net` won't resolve until Tailscale is back up.
- **Container died**: `docker logs hermes-relay --tail 100` → likely a port collision or a stale `OPERATOR_TOKEN` in the env. Recreate the container with the same `OPERATOR_TOKEN` as `~/.hermes/profiles/collector/.operator-token` (see Stage 3e).
- **Token rotation**: regenerate with `openssl rand -hex 32`, write to `relay/.operator-token-test`, restart the container with the new env, copy the new token to `~/.hermes/profiles/collector/.operator-token`, restart the operator CLI.

For more detail, see [docs/RUNBOOK.md](docs/RUNBOOK.md) and the `hermes-distribution-packaging` skill → **Tailscale-as-PC-relay**.

---

## Stage 8: Cut a new release (when you update the bundle)

```bash
cd ~/hermes-dist
# Make your changes (new skill, updated SOUL.md, etc.)

git add .
git commit -m "v0.2.0: add image-style-pipeline skill to catalog"
git tag v0.2.0
git push origin v0.2.0
```

Users who run `hermes update` get the new version. Security files (denylist, hooks) are auto-pulled silently. SOUL.md / config / new skills require `hermes update` confirmation.

---

## What I CANNOT do for you (be straight)

| Task | Why I can't do it |
|---|---|
| Push to GitHub | Need your GitHub login |
| `tailscale up` (authenticate) | Need your tailnet account |
| Invite a user to your tailnet | Need to share a node from your account |
| Build the macOS / Linux .dmg / .AppImage | I'm in a Windows terminal; cross-compile needs a Mac |

Everything else (the code, the deploy script, the test verification, the docs) is done.

## Time check

- Stage 0: 5 min (you)
- Stage 1: 5 min (you: install gh, login, create repo)
- Stage 2: 2 min (you: authenticate Tailscale)
- Stage 3: 5 min (mostly automated: build + start container + propagate token)
- Stage 4: 5 min (you: test the install)
- Stage 5: 30 sec
- **Total: ~20 min for end-to-end ship**

After that, you're in maintenance mode (5 min/day for review). No remote server to babysit — the relay lives on this box and wakes with it.
