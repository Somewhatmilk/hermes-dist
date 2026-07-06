# Hermes Dist — Operator Runbook

## Prerequisites (one-time)

You need:

- This PC (Windows 10+ with WSL or Git Bash, or macOS, or Linux)
- Docker installed (you have it: `docker --version` works)
- Python 3.11+ (you have it: `python3 --version` works)
- Git (you have it)
- An Oracle Cloud account (free signup at https://cloud.oracle.com/)
- A GitHub account (you have it)
- ~30 minutes for the initial setup, ~5 minutes for subsequent updates

You do NOT need:

- A domain name (the relay can run on the Oracle instance's public IP)
- A TLS certificate (Oracle instances have public IPs; you can add TLS later)
- A separate server (this is the PoC, your PC orchestrates + the relay is on Oracle)

## Step 1: Test locally (5 minutes)

Verify the relay code works on your PC before deploying anywhere.

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

If anything fails, the relay isn't ready to deploy. Don't proceed.

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

## Step 3: Provision Oracle Cloud (15-30 minutes, one-time)

1. Sign up at https://cloud.oracle.com/ (free, requires credit card for verification, you won't be charged)
2. Once logged in to the OCI console, navigate to **Compute → Instances → Create Instance**
3. Configure:
   - **Name**: `hermes-relay`
   - **Image**: Ubuntu 22.04 (or Oracle Linux 8)
   - **Shape**: `VM.Standard.A1.Flex` with `1 OCPU` and `6 GB RAM` (free tier allows up to 4 OCPU/24GB total)
   - **Networking**: create a new VCN, public subnet
   - **SSH keys**: upload your public key (`~/.ssh/id_rsa.pub` or generate a new one)
4. Click **Create**. Provisioning takes 1-2 minutes.
5. Note the **Public IP** of the instance.

### Open port 9119 in the VCN

1. In the OCI console, go to **Networking → Virtual Cloud Networks → (your VCN) → Subnets → (public subnet) → Security Lists → Default Security List**
2. Click **Add Ingress Rules**:
   - Source CIDR: `0.0.0.0/0`
   - Protocol: TCP
   - Destination Port: `9119`
3. Save.

## Step 4: Deploy the relay (5 minutes)

From your PC:

```bash
cd ~/hermes-dist
chmod 600 ~/path/to/your-oracle-key.pem   # SSH key must be 600

bash relay/deploy/deploy-oracle.sh ubuntu@<PUBLIC_IP> -i ~/path/to/your-oracle-key.pem
```

Replace `<PUBLIC_IP>` with the actual IP. Replace `ubuntu@` with `opc@` if you used Oracle Linux.

The script will:
1. Install Docker on the instance
2. Copy the relay files to `/opt/hermes-relay`
3. Generate a random `OPERATOR_TOKEN` and print it
4. Build + start the relay container
5. Install the systemd service + daily-ping timer
6. Print the public health check URL

**Save the OPERATOR_TOKEN** somewhere safe (password manager). You'll need it to query events.

Verify:

```bash
curl http://<PUBLIC_IP>:9119/api/v1/healthz
```

Should return:
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

## Step 5: Self-install (test the user flow) (5 minutes)

Install a hermes-dist user install on YOUR OWN machine in a separate directory to verify the end-to-end flow.

```bash
# In a test directory, NOT in your real ~/.hermes
mkdir ~/hermes-dist-test
cd ~/hermes-dist-test

# Copy the installer
cp ~/hermes-dist/install-windows.ps1 .
# or for Mac/Linux: cp ~/hermes-dist/install-unix.sh .

# Run with your relay URL
.\install-windows.ps1 -RelayUrl "http://<PUBLIC_IP>:9119" -DistRepo "https://github.com/you/hermes-dist"
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

1. Send them the `install-windows.ps1` (or `install-unix.sh` for Mac/Linux)
2. Tell them the relay URL and the dist repo URL
3. They run the installer
4. They decide whether to opt in to data forwarding
5. They launch the agent and use it

You can monitor their activity via:

```bash
hermes-distribution pull      # fetch new events
hermes-distribution list      # see what's pending
hermes-distribution review skills   # look at submitted skills
hermes-distribution health    # relay stats
```

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

Users running `hermes update` will see the new version. Their daily cron will pull the changes silently. Security files (denylist, hooks) are auto-applied. Other changes need `hermes update` (manual confirmation).

## Troubleshooting

### "The relay is unhealthy"

```bash
ssh ubuntu@<PUBLIC_IP> -i ~/oracle-key.pem
sudo systemctl status hermes-relay
sudo docker compose -f /opt/hermes-relay/docker-compose.yml ps
sudo docker compose -f /opt/hermes-relay/docker-compose.yml logs --tail 50
```

### "The user install can't reach the relay"

1. Verify the relay is up: `curl http://<PUBLIC_IP>:9119/api/v1/healthz` from the user's machine
2. Check the VCN security list has port 9119 open
3. Check the user's `~/.hermes/profiles/<uuid>/config.yaml` has the correct `remote:` URL
4. Have the user run `hermes distribution test` (if you've added that command)

### "The collector profile can't pull events"

1. Check the operator token file: `cat ~/.hermes/profiles/collector/.operator-token`
2. Verify it matches the relay: `curl -H "X-Operator-Token: $(cat ~/.hermes/profiles/collector/.operator-token)" http://<PUBLIC_IP>:9119/api/v1/healthz`
3. If the token is wrong, redeploy the relay (regenerates a new one) and update the local `.operator-token` file

### "A user is sending garbage / abusive events"

1. Find their UUID: `hermes-distribution list users`
2. SSH to the Oracle instance
3. Open the SQLite: `sqlite3 /var/lib/hermes-relay/relay.db`
4. `DELETE FROM users WHERE uuid = '<bad-uuid>';`
5. `DELETE FROM events WHERE uuid = '<bad-uuid>';`
6. The user's next request will get 401 (unknown user) and they'll see a sync failure
7. (To permanently block, you could add a `banned` column and a 403 response — not in the PoC)

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

# 5. Spot-check relay health
hermes-distribution health
```

## Weekly operations (30 minutes/week)

- Read the audit log: `sqlite3 /var/lib/hermes-relay/relay.db "SELECT * FROM audit_log ORDER BY ts DESC LIMIT 100;"`
- Review user growth: `hermes-distribution list users`
- Update the denylist if you see new exfil domains in the flagged scripts
- Update skills / SOUL.md if you want to ship a new feature
- Cut a release: `git tag v1.x.0 && git push --tags`
