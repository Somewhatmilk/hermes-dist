# hermes-dist

Distribution bundle for a hardened, distribution-safe Hermes Agent build.

This repo is what end users clone / `hermes update` from. It contains:

- `default-template/` — the user-facing profile bundle (the only profile a user receives)
- `relay/` — the FastAPI collector that receives signed events from user installs
- `docs/` — architecture, security model, and operator runbook

## TL;DR (for the operator — you)

```bash
# 1. Local dry-test (no GitHub, no remote server)
cd ~/hermes-dist
./relay/tests/dry-run.sh                  # builds the relay Docker, fires a signed test event,
                                          # writes the operator token to relay/.operator-token-test

# 2. Ship to a public GitHub repo
gh repo create you/hermes-dist --public --source=. --remote=origin --push
# (or: git remote add origin git@github.com:you/hermes-dist.git && git push -u origin main)

# 3. Bring Tailscale up on this PC (already installed at %LOCALAPPDATA%\Tailscale\)
tailscale up                              # sign in via browser, accept the node
tailscale ip -4                           # confirm 100.x.x.x + MagicDNS name

# 4. Deploy the relay to a local Docker container bound to 127.0.0.1:9119
#    (reached by users over Tailscale at https://<host>.tail.ts.net:9119)
cd ~/hermes-dist/relay
docker build -t hermes-relay:latest .
docker run -d --name hermes-relay --restart unless-stopped \
  -p 127.0.0.1:9119:9119 \
  -e OPERATOR_TOKEN="$(cat .operator-token-test)" \
  -v hermes-relay-data:/var/lib/hermes-relay \
  hermes-relay:latest

# 5. Propagate the operator token to your operator profile
mkdir -p ~/.hermes/profiles/collector
cp .operator-token-test ~/.hermes/profiles/collector/.operator-token
chmod 600 ~/.hermes/profiles/collector/.operator-token

# 6. Point a user install at the relay
hermes install --from you/hermes-dist --relay https://<host>.tail.ts.net:9119
```

The relay runs on **this box**. No remote VPS, no public IP, no SSH bastion — Tailscale's WireGuard over DERP gives you a stable 100.x.x.x + `<host>.tail.ts.net` for free. When you eventually move to a NAS or VPS, you only flip the DNS name; users' `gateway_config.json` is unchanged. See the `hermes-distribution-packaging` skill → **Tailscale-as-PC-relay** and **Migration PC → NAS via DNS entrypoint**.

## What end users see

The user clones the repo (or runs the Windows installer), executes `.onboard.sh`
or `install-windows.ps1`, gets a UUID + opt-in prompt. If they opt in, their
agent's `default` profile periodically sends signed events to the relay:

- New skills they've written
- Memories they mark `submit_to_collector: true`
- Scripts that triggered the denylist (flagged, blocked from execution)
- Diff of their per-profile `SOUL.md` / `config.yaml` (read-only audit trail)

The operator (`you`) reviews submissions by launching the `collector` profile
on this box:

```bash
hermes -p collector chat
# "show me flagged scripts from the last 7 days"
# "approve skill X for inclusion in main"
```

## Security model (one paragraph)

Each user install has the `terminal` toolset disabled and a `pre-tool.sh` hook
that re-checks every tool call against an allowlist at the shell layer (not
config layer — prompt-injection-resistant). Scripts the user writes are
scanned by `post-skill-create.sh` against a denylist of hermes-touching and
exfiltration patterns. Flagged scripts are quarantined; clean ones run in
the local `code_execution` sandbox. The relay only accepts HMAC-signed
payloads from UUIDs that exist in the registry table.

## File layout

```
hermes-dist/
├── README.md                              this file
├── .onboard.sh                            per-user first-launch script
├── default-template/                      the user-facing profile bundle
│   ├── profile.yaml
│   ├── config.yaml
│   ├── SOUL.md                            sanitized for distribution
│   ├── hooks/
│   │   ├── pre-tool.sh                    shell-layer tool allowlist
│   │   ├── post-skill-create.sh           script denylist + quarantine
│   │   └── post-memory-save.sh            marked-memory forwarder
│   ├── security/
│   │   ├── denylist.yaml                  script + URL + path patterns
│   │   └── allowlist.yaml                 permitted tools + paths
│   └── scripts/
│       └── uuidgen.sh                     portable UUIDv4 generator
├── install-windows.ps1                    PoC single-OS installer
├── install-unix.sh                        Mac/Linux installer (mirror of install-windows.ps1)
├── relay/                                 the FastAPI collector (runs locally on this PC)
│   ├── app/
│   │   ├── main.py
│   │   ├── hmac_auth.py
│   │   ├── sqlite_store.py
│   │   └── models.py
│   ├── deploy/                             historical — see SHIP.md for the current Tailscale flow
│   │   ├── deploy-oracle.sh                (Oracle Always Free ARM deploy — superseded)
│   │   ├── relay.service                   systemd unit
│   │   ├── relay-ping.timer                systemd timer
│   │   └── daily-ping.sh                   (Oracle reclamation defense — no longer needed)
│   ├── tests/
│   │   ├── dry-run.sh                      builds the Docker image and runs the 4-case test suite;
│   │   │                                   also writes the operator token to .operator-token-test
│   │   └── fire-test-event.sh
│   ├── Dockerfile
│   └── requirements.txt
└── docs/
    ├── ARCHITECTURE.md
    ├── SECURITY.md
    └── RUNBOOK.md
```

The `relay/deploy/deploy-oracle.sh` script is kept for reference (in case the operator
later wants to provision a cloud VM) but the supported ship path is the
Tailscale-on-this-PC flow described in [SHIP.md](SHIP.md) Stage 2-3. Tailscale
gives a stable `<host>.tail.ts.net` and WireGuard encryption without exposing
the operator's ISP IP; the relay stays on this box, bound to 127.0.0.1.

## License

Internal PoC. Do not redistribute the `default-template/security/denylist.yaml`
without the operator's sign-off.
