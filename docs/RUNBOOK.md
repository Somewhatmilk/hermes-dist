# Hermes Dist — Operator Runbook

## Prerequisites (one-time)

You need:

- This PC (Windows 10+ with WSL or Git Bash, or macOS, or Linux)
- Docker installed (you have it: `docker --version` works)
- Python 3.11+ (you have it: `python3 --version` works)
- Git (you have it)
- Tailscale installed on this PC (Windows: already at `%LOCALAPPDATA%\Tailscale\`)
- A Tailscale account (free at https://login.tailscale.com — Google / Microsoft / GitHub SSO)
- A GitHub account (you have it)
- ~20 minutes for the initial setup, ~5 minutes for subsequent updates

You do NOT need:

- A remote server (the relay runs on this PC, behind Tailscale)
- A domain name (Tailscale MagicDNS gives you `<host>.tail.ts.net` for free)
- A TLS certificate (WireGuard encrypts the transport; HTTPS terminates at the relay)
- A public IP from your ISP (Tailscale hands out 100.x.x.x and routes through DERP relays)

The relay runs on **this box** and is reached by users over Tailscale at
`https://<host>.tail.ts.net:9119`. This is the "operator's PC is the deploy
target" pattern documented in the `hermes-distribution-packaging` skill under
**Tailscale-as-PC-relay**. When you eventually move to a NAS or VPS, only the
MagicDNS name changes; users' `gateway_config.json` is unchanged — see
**Migration PC → NAS via DNS entrypoint** in the same skill.

## Step 1: Test locally (5 minutes)

Verify the relay code works on your PC before exposing it to Tailscale.

```bash
cd ~/hermes-dist/relay
bash tests/dry-run.sh
```

You should see:

```
→ Building Docker image...
→ Starting container...
  ✓ Healthy after 2s
→ Running test event script...
  ✓ Event accepted
  ✓ Replay rejected
  ✓ Bad signature rejected
=== All test cases passed ===
```

The script also writes the freshly-generated `OPERATOR_TOKEN` to
`relay/.operator-token-test` (chmod 600 by convention; you do that manually in
Step 4). **Don't lose this token** — it's the only way to query events as the
operator.

If anything fails, the relay isn't ready to expose. Don't proceed.

## Step 2: Push to GitHub (2 minutes)

This makes the bundle accessible to user installs.

```bash
# One-time: install gh CLI
winget install --id GitHub.cli  # Windows
brew install gh                  # macOS
sudo apt install gh              # Linux

# Authenticate
gh auth login
# → GitHub.com → HTTPS → browser

# Create the public repo
cd ~/hermes-dist
gh repo create you/hermes-dist --public --source=. --remote=origin --push
# Replace `you` with your actual GitHub username
```

You should now have a public repo at `github.com/you/hermes-dist`.

## Step 3: Bring Tailscale up on this PC (2 minutes)

Tailscale is already installed at `%LOCALAPPDATA%\Tailscale\` on Windows. You
just need to authenticate and verify MagicDNS is serving your hostname.

```bash
# Start the Tailscale daemon if it isn't already running
tailscale up

# Verify
tailscale status
# → 100.x.x.x   <host>   <user>@   windows   ...

tailscale ip -4
# → 100.x.x.x
```

`%LOCALAPPDATA%\Tailscale\tailscale-status.json` shows the registered node.
The `<host>` segment comes from your Windows hostname; rename the PC before
`tailscale up` if you want a different MagicDNS name. Underscores are not
allowed; hyphens are.

**Set the auto-start preference.** In the Tailscale tray → **Preferences**:

- ☑ **Run Tailscale when computer starts**

This is what makes the wake-from-sleep recipe from the skill work without
operator intervention: power on the PC → Tailscale auto-handshakes → Docker
auto-starts → relay container restarts → users can reach the gateway.

If your hostname is, say, `somew-pc`, then your MagicDNS entrypoint is
`somew-pc.tail.ts.net`. From now on, the relay URL you give to users is
`https://somew-pc.tail.ts.net:9119` (substitute your own `<host>` everywhere).

## Step 4: Deploy the relay on this PC + propagate the operator token (5 minutes)

```bash
cd ~/hermes-dist/relay

# 1. Build the image
docker build -t hermes-relay:latest .

# 2. (Re)generate the operator token if you skipped Step 1
#    OR if you want to rotate the token from a previous install
export OPERATOR_TOKEN=$(openssl rand -hex 32)
echo "$OPERATOR_TOKEN" > .operator-token-test
chmod 600 .operator-token-test

# 3. Start the container, bound to localhost only (Tailscale handles the rest)
docker run -d --name hermes-relay \
  --restart unless-stopped \
  -p 127.0.0.1:9119:9119 \
  -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
  -v hermes-relay-data:/var/lib/hermes-relay \
  hermes-relay:latest

# 4. Verify on localhost
curl -s http://127.0.0.1:9119/api/v1/healthz
# → {"ok": true, "version": "hermes-relay-0.1.0", "uptime_seconds": 12.4, ...}

# 5. Verify on the Tailscale entrypoint (substitute your <host>)
curl -s https://<host>.tail.ts.net:9119/api/v1/healthz
# → same JSON, proving Tailscale is routing correctly
```

### Propagate the operator token to the operator's hermes profile

The relay is live, but `hermes-distribution pull` / `list` / `review` need the
token at a known path on the operator's side. Wire it once now:

```bash
# PowerShell-native
$opProfile = "$env:USERPROFILE\.hermes\profiles\collector"
New-Item -ItemType Directory -Force -Path $opProfile | Out-Null
Copy-Item .\relay\.operator-token-test "$opProfile\.operator-token" -Force
icacls "$opProfile\.operator-token" /inheritance:r /grant:r "$env:USERNAME:(R,W)" | Out-Null
```

```bash
# Bash / Git Bash equivalent
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

**If you ever rotate the token:** repeat steps 2-5 above (regenerate, restart
the container, copy to the operator profile). The token is the only thing
that authorises operator-side reads; loss of this file means re-issue +
re-distribute.

## Step 5: Self-install (test the user flow) (5 minutes)

Install a hermes-dist user install on YOUR OWN machine in a separate
directory to verify the end-to-end flow.

```bash
# In a test directory, NOT in your real ~/.hermes
mkdir ~/hermes-dist-test
cd ~/hermes-dist-test

# Copy the installer
cp ~/hermes-dist/install-windows.ps1 .
# or for Mac/Linux: cp ~/hermes-dist/install-unix.sh .

# Run with your Tailscale entrypoint
.\install-windows.ps1 -RelayUrl "https://<host>.tail.ts.net:9119" -DistRepo "https://github.com/you/hermes-dist"
```

This will:
1. Verify Python + Git + Docker
2. Install Hermes if not present
3. Clone the dist repo
4. Run `.onboard.sh` (UUID gen, opt-in prompt, hooks wiring)
5. Start the tinysearch Docker container
6. Register a Windows Task Scheduler daily-update job
7. Print a summary

Test the agent by launching it:

```bash
hermes -p <your-uuid> chat
```

Ask it to do something. Verify:
- It CAN write a file to `~/Documents/test/`
- It CANNOT write to `~/.hermes/`
- It CANNOT run a shell command
- It DOES log every tool call to `audit.log`

Then test the data flow:

```bash
# As the test user
echo "test memory" | hermes -p <your-uuid> memory add --metadata '{"submit_to_collector": true}'

# As the operator
hermes-distribution pull
hermes-distribution list
hermes-distribution review memories
```

The test memory should appear in `~/.hermes/profiles/collector/quarantine/memories/`.

## Step 6: Production rollout (one user at a time)

For each real user:

1. **Invite them to your tailnet.** Tailscale → Access Controls → invite, or
   share a node from your account. Without this, `<host>.tail.ts.net` is
   unreachable from their machine — that's the point of Tailscale (your ISP
   IP never appears in their config).
2. Send them the `install-windows.ps1` (or `install-unix.sh` for Mac/Linux)
3. Tell them the relay URL (`https://<host>.tail.ts.net:9119`) and the dist
   repo URL (`https://github.com/you/hermes-dist`)
4. They run the installer
5. They decide whether to opt in to data forwarding
6. They launch the agent and use it

You can monitor their activity via:

```bash
hermes-distribution pull      # fetch new events from the local relay
hermes-distribution list      # see what's pending
hermes-distribution review skills   # look at submitted skills
hermes-distribution health    # relay stats
```

### If you want a user on the public internet (not on your tailnet)

Enable Tailscale Funnel for port 9119 — this routes their traffic through
Tailscale's DERP relays, so your ISP IP is still hidden:

```bash
tailscale serve --bg --https=9119 http://localhost:9119
tailscale funnel --bg --https=9119 http://localhost:9119
```

Only enable Funnel for users who explicitly opt in to a public-internet
connection. The default is tailnet-only (safer). See the skill's
**Tailscale-as-PC-relay** section for the Funnel pitfall list.

## Step 7: Cut a release (when you update the bundle)

```bash
cd ~/hermes-dist
# Make your changes (e.g. add a new skill to default-template/skills/, update SOUL.md, etc.)

# Commit + tag
git add .
git commit -m "v1.1.0: add image-style-pipeline skill to catalog"
git tag v1.1.0
git push --tags
```

Users running `hermes update` will see the new version. Their daily cron will
pull the changes silently. Security files (denylist, hooks) are
auto-applied. Other changes need `hermes update` (manual confirmation).

## Troubleshooting

### "The relay is unhealthy"

```bash
# Container state
docker ps --filter name=hermes-relay --format '{{.Status}}'
docker logs hermes-relay --tail 50

# Tailscale state
tailscale status
tailscale ping <host>.tail.ts.net

# Direct localhost check
curl -s http://127.0.0.1:9119/api/v1/healthz
```

If the container died, the most common cause is a port collision or a stale
`OPERATOR_TOKEN` in the env. Recreate the container with the same
`OPERATOR_TOKEN` as `~/.hermes/profiles/collector/.operator-token` (see
Step 4).

### "The user install can't reach the relay"

1. Verify the relay is up: `curl -s https://<host>.tail.ts.net:9119/api/v1/healthz`
2. Verify Tailscale on the user's machine: `tailscale status` (should show
   your `<host>` as a peer)
3. Check the user's `~/.hermes/profiles/<uuid>/config.yaml` has the correct
   `remote:` URL
4. Have the user run `tailscale ping <host>.tail.ts.net` — if it fails, the
   tailnet invite hasn't propagated or the user installed Tailscale under a
   different account
5. Have the user run `hermes distribution test` (if you've added that command)

### "The collector profile can't pull events"

1. Check the operator token file: `cat ~/.hermes/profiles/collector/.operator-token`
2. Verify it matches the relay: `curl -H "X-Operator-Token: $(cat ~/.hermes/profiles/collector/.operator-token)" https://<host>.tail.ts.net:9119/api/v1/healthz`
3. If the token is wrong, regenerate (Step 4, sub-step 2), restart the
   container with the new env, and update the local `.operator-token` file

### "A user is sending garbage / abusive events"

1. Find their UUID: `hermes-distribution list users`
2. Open the SQLite directly (it's a Docker volume on this PC):
   `docker exec -it hermes-relay sqlite3 /var/lib/hermes-relay/relay.db`
3. `DELETE FROM users WHERE uuid = '<bad-uuid>';`
4. `DELETE FROM events WHERE uuid = '<bad-uuid>';`
5. The user's next request will get 401 (unknown user) and they'll see a sync
   failure
6. (To permanently block, you could add a `banned` column and a 403 response
   — not in the PoC)

### "Tailscale logged out / node is offline"

1. Open the Tailscale tray app, re-authenticate
2. `tailscale up` to re-confirm the node is registered
3. The relay container itself keeps running on `127.0.0.1:9119` and is still
   reachable locally, but `<host>.tail.ts.net` won't resolve until Tailscale
   is back up. Users see a brief outage (~30s to a few minutes depending on
   DERP latency)

### "PC was asleep, now the relay isn't responding"

This is expected ~45-sec wake handshake. Wait, then re-check. If it persists:

```bash
docker ps --filter name=hermes-relay
# If container is missing: docker start hermes-relay
# If container is exited: docker logs hermes-relay --tail 100
```

The container's `restart: unless-stopped` policy means it auto-resurrects on
the next daemon restart, but a Docker Desktop crash or full Windows reboot
may not trigger it. Set Docker Desktop → **Start Docker Desktop when you
sign in** to ON (Step 3 has the same setting for Tailscale).

## Daily operations (5 minutes/day)

```bash
# 1. Pull new events
hermes-distribution pull

# 2. Check what's pending
hermes-distribution list

# 3. Review anything that looks interesting
hermes-distribution review scripts

# 4. Approve / reject
hermes-distribution approve quarantine/skills/clean/foo.json
hermes-distribution reject quarantine/skills/flagged/bar.json "credential-theft pattern"

# 5. Spot-check relay health (and that it survived any reboots)
docker ps --filter name=hermes-relay --format '{{.Status}}'
tailscale status
curl -s https://<host>.tail.ts.net:9119/api/v1/healthz
```

## Weekly operations (30 minutes/week)

- Read the audit log: `docker exec hermes-relay sqlite3 /var/lib/hermes-relay/relay.db "SELECT * FROM audit_log ORDER BY ts DESC LIMIT 100;"`
- Review user growth: `hermes-distribution list users`
- Update the denylist if you see new exfil domains in the flagged scripts
- Update skills / SOUL.md if you want to ship a new feature
- Cut a release: `git tag v1.x.0 && git push --tags`
- If you're approaching the comfort limit for the "PC is the relay" pattern
  (frequent shutdowns, user complaints about the 45-sec wake window), plan
  the NAS/VPS migration following the skill's **Migration PC → NAS via DNS
  entrypoint** recipe
