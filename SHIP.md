# Hermes Dist — Ship Runbook

**This is the concrete sequence of commands to go from "code on your laptop" to "users on the internet can install it".**

Estimated total time: **45 minutes** (15 min for the parts that need your hands on the keyboard, 30 min for the parts where you wait for Oracle to provision).

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

## Stage 2: Provision Oracle Cloud (15-25 min, mostly waiting)

### 2a. Sign up

1. Go to https://cloud.oracle.com/
2. Click "Start for Free"
3. Provide email, password, account name (e.g. "hermes-dist-poc")
4. Select a home region (pick the one closest to your users — US East, EU Frankfurt, etc.)
5. **Credit card verification required.** You won't be charged. The card is just to prevent abuse.
6. Wait for the tenancy to provision (usually <5 min)

### 2b. Create a VCN with port 9119 open

The VCN (Virtual Cloud Network) is your private network in Oracle. You need one before the instance.

1. In OCI console, click the hamburger menu (☰) → **Networking → Virtual Cloud Networks**
2. Click **Start VCN Wizard → Create VCN with Internet Connectivity**
3. Name: `hermes-vcn`
4. CIDR: `10.0.0.0/16` (default)
5. Subnet: `10.0.1.0/24` (default, public)
6. Click **Next → Create**

Now open port 9119:

1. Click on your VCN → **Subnets → Public Subnet (default) → Default Security List**
2. Click **Add Ingress Rules**:
   - **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** TCP
   - **Destination Port Range:** `9119`
3. Click **Add Ingress Rules** again to save.

### 2c. Create the instance

1. Hamburger menu → **Compute → Instances → Create Instance**
2. **Name:** `hermes-relay`
3. **Placement:** leave default (your home region)
4. **Image:** Ubuntu 22.04 (or Oracle Linux 8 — Ubuntu has a friendlier first-deploy)
5. **Shape:** Click **Edit → Ampere A1** → Select `VM.Standard.A1.Flex` with **1 OCPU** and **6 GB RAM**
6. **Networking:** select the VCN and public subnet you just created
7. **SSH Keys:** Choose **Generate a key pair** OR **Upload public key** (e.g. `~/.ssh/id_rsa.pub` from your box)
   - If generating: **download the private key** (e.g. `ssh-key-2026-XX-XX.key`) and save it somewhere safe. You'll need it.
   - If uploading: copy your public key from `~/.ssh/id_rsa.pub` (use `cat` to view it)
8. **Boot volume:** leave default (47 GB, free tier)
9. Click **Create**

Provisioning takes 1-2 minutes. The state will be PROVISIONING → RUNNING.

Note the **Public IP** of the instance (visible in the instance details).

### 2d. Wait + verify SSH

```bash
# Set restrictive perms on your key
chmod 600 ~/Downloads/ssh-key-*.key

# Try to SSH (default user is 'ubuntu' for Ubuntu images, 'opc' for Oracle Linux)
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<PUBLIC_IP> "echo 'connected' && uname -a"
```

You should see a "connected" message and Linux kernel info.

---

## Stage 3: Deploy the relay (5 min, mostly automated)

```bash
cd ~/hermes-dist
bash relay/deploy/deploy-oracle.sh ubuntu@<PUBLIC_IP> -i ~/Downloads/ssh-key-*.key
```

This script will:
1. Install Docker on the instance (~1-2 min)
2. Copy the relay files to `/opt/hermes-relay`
3. Generate a random `OPERATOR_TOKEN` and print it
4. Build the Docker image
5. Start the relay container
6. Install the systemd service + daily-ping timer (Oracle reclamation defense)

**The script prints a final summary. Save the OPERATOR_TOKEN immediately** — it's the only way to query events.

```bash
# Save the token
echo "<TOKEN_FROM_OUTPUT>" > ~/.hermes/profiles/collector/.operator-token
chmod 600 ~/.hermes/profiles/collector/.operator-token
```

### Verify the relay

From your laptop:
```bash
curl http://<PUBLIC_IP>:9119/api/v1/healthz
```

Expected:
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
- The OCI security list has port 9119 open (Stage 2b)
- The container is running: `ssh ubuntu@<PUBLIC_IP> "docker ps"`
- The instance is reachable: `ping <PUBLIC_IP>`

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
.\install-windows.ps1 -RelayUrl "http://<PUBLIC_IP>:9119" -DistRepo "https://github.com/you/hermes-dist"
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
- The relay URL (e.g. `http://<PUBLIC_IP>:9119`)
- The dist repo URL (`https://github.com/you/hermes-dist`)

The instructions to give them:
```powershell
# Windows (PowerShell)
.\install-windows.ps1 -RelayUrl "http://<PUBLIC_IP>:9119" -DistRepo "https://github.com/you/hermes-dist"
```

```bash
# Mac/Linux
curl -O https://raw.githubusercontent.com/you/hermes-dist/main/install-unix.sh
chmod +x install-unix.sh
./install-unix.sh https://github.com/you/hermes-dist http://<PUBLIC_IP>:9119
```

They decide whether to opt in to data forwarding. Default: **opt-out** (no data leaves their box).

---

## Stage 7: Daily operations (5 min/day)

```bash
# 1. Pull new events from relay
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

# 5. Check relay health
hermes-distribution health
```

For more detail, see [docs/RUNBOOK.md](docs/RUNBOOK.md).

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
| Provision Oracle | Need your credit card + OCI login |
| SSH into Oracle | Instance doesn't exist yet |
| Create a GitHub PAT | Need your GitHub login |
| Build the macOS / Linux .dmg / .AppImage | I'm in a Windows terminal; cross-compile needs a Mac |

Everything else (the code, the deploy script, the test verification, the docs) is done.

---

## Time check

- Stage 0: 5 min (you)
- Stage 1: 5 min (you: install gh, login, create repo)
- Stage 2: 15-25 min (mostly waiting for Oracle)
- Stage 3: 5 min (mostly automated)
- Stage 4: 5 min (you: test the install)
- Stage 5: 30 sec
- **Total: 35-45 min for end-to-end ship**

After that, you're in maintenance mode (5 min/day for review).
