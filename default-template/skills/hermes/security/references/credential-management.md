## Credential Management

This user has a **self-hosted / encrypted / Cryptomator / anonymous-per-account** profile. They default to local encryption over cloud. Recommend local-first; only escalate to GCP/AWS Secret Manager when the user explicitly wants cross-machine access.

### Option A (default for this user): `pass` — GPG-encrypted Unix password manager

Pure local. Zero cloud account. Zero billing. Native on Linux + Mac + Windows, supports `pass git init` for multi-device sync, integrates with QtPass / pass-winmenu / rofi-pass for GUI/copy workflows.

**Why this was switched from age (2026-07-05):**

- User wants **multi-platform** (Linux, Mac, Windows) — `pass` ships native, age does not.
- User wants **multi-device sync** — `pass` uses `git`, age needs the key file copied manually.
- `pass` requires a **GPG passphrase** to decrypt each entry; age unlocks with a keyfile alone (lower bar for an attacker who lands on the key file).
- Setup path: see `templates/hermes-pass-init-checklist.md`.
- Threat ranking: see `references/credential-4-rung-ladder-2026.md`.

### Option B: `op-env` (1Password CLI) — when user is already paying for 1Password

Same threat model as `pass` but with biometric unlock, web vault UI, and team sharing. Trade: $5-15/seat/mo, requires 1Password account.

### Option C: HashiCorp Vault — only for cloud-hosted agents with multiple service identities

$30k-80k/yr enterprise tier. Dynamic credentials, workload identity, full audit log. Overkill for solo dev on a laptop.

### Option D: GPG-encrypted env var file (legacy, only if `pass` cannot be installed)

Use the existing `gpg-symmetric` path. Same threat model as Option A but no per-entry granularity — one bad file = all secrets leak.

## Section Index

| Topic | Reference |
|---|---|
| Credential Management (this file, default: pass) | `references/credential-management.md` |
| **4-rung credential ladder + 2026 incident evidence** | `references/credential-4-rung-ladder-2026.md` |
| **pass install + init + 12-key migration** | `templates/hermes-pass-init-checklist.md` |
| Approval Safety | `references/approval-safety.md` |
| Threat Model | `references/threat-model.md` |
| Secret Leak Workflow + Prevention | `references/secret-leak-workflow.md` |
| Verification | `references/verification.md` |
| Hold Their Secrets | `references/hold-their-secrets.md` |
| Electron App Audit | `references/electron-app-audit.md` |
| Untrusted Binary | `references/untrusted-binary.md` |
| API-Key Patterns (4-pattern taxonomy) | see `hermes-redaction-bypass/references/api-key-patterns.md` |

## Changelog

- **v2.1.0 (2026-07-05):** Default switched from `age` → `pass` (decision 2026-07-05). Rationale: multi-platform support + multi-device sync + passphrase-protected at rest. Age templates soft-deleted from this skill, `hermes-session-ritual/templates/`, and `~/.hermes/scripts/`. New install + migration guide in `templates/hermes-pass-init-checklist.md`. New threat-ranking reference in `references/credential-4-rung-ladder-2026.md`.
- **v2.0.0 (2026-07-02):** Refactored 36,471 to ~3KB body. Snapshot at `~/Downloads/refactor_2026-07-02/hermes-security-hardening_BACKUP.md`.
