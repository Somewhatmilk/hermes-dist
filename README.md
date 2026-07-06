# hermes-dist

Distribution bundle for a hardened, distribution-safe Hermes Agent build.

This repo is what end users clone / `hermes update` from. It contains:

- `default-template/` — the user-facing profile bundle (the only profile a user receives)
- `relay/` — the FastAPI collector that receives signed events from user installs
- `docs/` — architecture, security model, and operator runbook

## TL;DR (for the operator — you)

```bash
# 1. Local dry-test (no GitHub, no Oracle)
cd ~/hermes-dist
./relay/tests/dry-run.sh                  # builds the relay Docker, fires a signed test event

# 2. Ship to a public GitHub repo
gh repo create you/hermes-dist --public --source=. --remote=origin --push
# (or: git remote add origin git@github.com:you/hermes-dist.git && git push -u origin main)

# 3. Deploy the relay to Oracle Cloud Always Free ARM
./relay/deploy/deploy-oracle.sh <oracle-instance-public-ip>

# 4. Point a user install at the relay
hermes install --from you/hermes-dist --relay https://relay.your-domain
```

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
├── relay/                                 the FastAPI collector
│   ├── app/
│   │   ├── main.py
│   │   ├── hmac_auth.py
│   │   ├── sqlite_store.py
│   │   └── models.py
│   ├── deploy/
│   │   ├── deploy-oracle.sh
│   │   ├── relay.service                  systemd unit
│   │   └── daily-ping.sh                  Oracle-reclamation-defense
│   ├── tests/
│   │   ├── dry-run.sh
│   │   └── fire-test-event.sh
│   ├── Dockerfile
│   └── requirements.txt
└── docs/
    ├── ARCHITECTURE.md
    ├── SECURITY.md
    └── RUNBOOK.md
```

## License

Internal PoC. Do not redistribute the `default-template/security/denylist.yaml`
without the operator's sign-off.
