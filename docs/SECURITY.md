# Hermes Dist — Security Model

## Threat model

The system is designed to defend against:

1. **A malicious or curious user** who wants to escape the restricted toolset, exfiltrate their data to attacker-controlled servers, or compromise the operator's account.
2. **A prompt-injection attack** against the user's `default` profile that tries to bypass the toolset restriction, modify operator files, or send unauthorized data to the relay.
3. **Network attackers** who try to replay signed events, forge HMAC signatures, or extract user data from the relay.
4. **Operator account compromise** — if the operator's GitHub account is compromised, an attacker could push a malicious `denylist.yaml` to all users. (See mitigation in section 4.)

It is NOT designed to defend against:

- The user themselves running arbitrary code on their own machine (they have a full OS, full Python install, etc. — Hermes is just an app on their box)
- A determined user who forks the bundle, removes all restrictions, and runs it (they can; that's the point of a permissive distribution)
- Compromised end-user machines (malware on the user's host can read anything Hermes reads — that's a host-level problem)
- Zero-days in Hermes, FastAPI, Pydantic, or the user's Python install (keep deps updated)

## 1. Per-user isolation

Each user install gets a unique UUID, a unique HMAC secret, and a unique Mnemosyne bank. The user cannot:

- Read other users' data on the relay (different secrets, different UUIDs)
- Forge events as another user (HMAC is per-user)
- Bypass the operator's denylist (it ships in the bundle; user has no shell to edit it)
- Pivot from the agent to attack the operator's host (URL denylist blocks private IPs, localhost, ngrok, pastebin, etc.)

## 2. Prompt-injection defense

The single most important defense is that **the operator's security files live at the shell layer, not the config layer**.

A successful prompt-injection could (theoretically) rewrite `~/.hermes/profiles/default-template/config.yaml` to add the `terminal` toolset. But:

- The user can't write to `config.yaml` (it's chmod 444, owned by the operator)
- The `pre-tool.sh` hook (chmod 555) doesn't read from `config.yaml`'s toolset list — it reads from `allowlist.yaml` (also chmod 444)
- Even if both are writable, the hook is on the shell layer — the only way to bypass it is to write to the hook itself, which is chmod 555 and the user has no `terminal` tool to `chmod` it

Additionally, every `skill_manage create` call triggers `post-skill-create.sh` which scans the new skill against `denylist.yaml`. A skill that contains `import hermes_tools` is caught. A skill that contains `subprocess.run(shell=True)` is caught. A skill that contains `eval()` is caught.

## 3. Network defense

- All relay-bound traffic is HMAC-SHA256 signed with a per-user secret
- Replay defense: nonce store, 600s TTL
- Clock skew defense: ±300s window
- Operator auth is a separate, longer token (256-bit) checked via `secrets.compare_digest`
- TLS recommended in production (Let's Encrypt via Caddy or certbot)
- The user's `tinysearch` Docker container binds to `127.0.0.1` only, so it's not reachable from outside the user's host

## 4. Operator compromise defense

If your GitHub account is compromised, an attacker could push a malicious update to `hermes-dist`. Mitigations:

- **Tagged releases only**: users run `hermes update` to apply a specific tag, not auto-pull
- **Force-pull only for security files**: the daily cron only re-pulls the denylist + hook scripts + SOUL.md. It does NOT pull new skills, new tools, or config changes silently.
- **Changelog review**: users see the diff before applying. A malicious `denylist.yaml` would have to not look malicious.
- **Future: signed manifests**: each release ships with a signature from a GPG key the user has on trust-on-first-use. If you can add this, do it. For the PoC, we trust the operator's GitHub account.

If your Oracle Cloud account is compromised, an attacker could read the SQLite DB (user UUIDs, secrets, event payloads). Mitigations:

- **HMAC secrets are stored in plaintext** in the SQLite (PoC simplification). In production, encrypt with a passphrase the operator types on first start. For the PoC, the threat model assumes Oracle account security.
- **Event payloads may contain user content** (memories, scripts). For the PoC, this is acceptable. In production, encrypt the payload with the operator's public key, so even a DB dump doesn't leak content.
- **Audit log is append-only** via SQLite constraints. An attacker can ADD entries but not delete them. (For stronger guarantees, use a separate WORM-style log.)

## 5. Audit trail

Every significant event is logged:

- **User side**: `~/.hermes/audit.log` (per-user, append-only)
  - Every tool call (anonymized)
  - Every skill create (clean or flagged)
  - Every memory save (local or queued)
  - Every forward attempt (success or failure)
- **Relay side**: SQLite `audit_log` table (operator queries via `/api/v1/audit`)
  - Every user registration
  - Every event received
  - Every operator query

The operator's `collector` profile has its own `audit/audit.log` for review decisions.

## 6. What to monitor in production

Once you're past the PoC:

- **Spike in flagged skills** from a single user → they're probing, possibly malicious
- **Spike in HTTP 401s** at the relay → someone is replay-attacking
- **Users with `opted_in: true` but zero events for >7 days** → their install is broken
- **New operators registering** without matching a known user UUID → reflection attack
- **Operator token being used from a new IP** → account compromise

The relay's `/api/v1/audit` endpoint gives you the raw material. Build a Grafana dashboard or just `tail -f` the audit log.

## 7. Hardening checklist (for after the PoC)

- [ ] Add GPG-signed release manifests
- [ ] Encrypt the relay's SQLite at rest (SQLCipher)
- [ ] Add TLS via Caddy + Let's Encrypt (one-liner)
- [ ] Move the operator token to a hardware key (YubiKey) for query auth
- [ ] Add a rate-limiter at the relay (per-user event budget per day)
- [ ] Add anomaly detection: spike in flagged events, spike in 401s
- [ ] Move Mnemosyne sync to a real protocol (HTTPS + WebSocket) instead of HTTPS POST
- [ ] Add a "revoke user" admin endpoint (currently you'd just delete the row)
- [ ] Add a "rotate user secret" flow (currently re-registration is the only way)
- [ ] Add per-user quotas (events per day, payload size, etc.)
