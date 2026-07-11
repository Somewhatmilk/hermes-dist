# Changelog — `security` skill

## `hermes-security-hardening` changelog (predecessor)

- **v1.8.0 (2026-07-06):** Reconciled the v1.7.0 changelog claim with
  the actual file state. The v1.7.0 entry promised §11
  "Windows-specific bugfixes", §12 "End-to-end smoke test procedure",
  and a `scripts/pass_source_smoke_test.py` file — none of which
  actually existed. All three are now real.
- **v1.7.0 (2026-07-06):** User-facing validation pass on the
  `pass_source.py` plugin. 4 Windows-specific bugs found and fixed:
  1. `resolve_dotenv_pointers()` crashed on `str` input →
     coerce `env_path` to `Path` at function entry.
  2. `find_pass()` returned None when `pass` is installed at
     `~/bin/pass` (no .exe) and not on PATH → add `~/bin/pass.exe`
     AND `~/bin/pass` to the Windows candidate list.
  3. `subprocess.run([pass, "show", X])` failed with
     `[WinError 193] %1 is not a valid Win32 application` on Windows
     → invoke through `bash` explicitly.
  4. Post-restart cache-staleness: when env_loader.py / pass_source.py
     edits land AFTER the gateway restart, the running process has
     the OLD module loaded in memory. User must `hermes gateway
     restart` again to pick up the fix.
- **v1.6.0 (2026-07-06):** User rejected the wrapper-script pattern.
  Canonical answer is now the in-process `pass_source.py` plugin in
  `agent/secret_sources/`, wired into
  `hermes_cli/env_loader.py:_apply_external_secret_sources()`.
  Launcher pattern demoted to "fallback for non-Hermes processes."
- **v1.5.0 (2026-07-05):** New `references/env-pointer-pattern.md` —
  the r/hermesagent canonical answer to the self-jailbreak incident.
  `.env` should contain `pass:api/X` pointers, NOT real values. A
  launcher script (`hermes-with-secrets.sh`) outside Hermes's reach
  resolves them at process start. Central pitfall: python-dotenv is a
  literal parser and does NOT evaluate `$(pass show ...)`. New
  `references/reddit-r-hermesagent-credential-patterns.md` — sourced
  excerpts from the three threads (self-jailbreak, Hermes+Bitwarden,
  Storing secrets).
- **v1.4.0 (2026-07-05):** `references/pass-batch-migration-recipe.md`
  — Step 2 loader decrypt line: dropped `--batch` and
  `--pinentry-mode loopback` (mutually exclusive on decrypt, return 0
  bytes silently). Added secure-delete pattern for tmpfile before
  unlink. `references/gpg-gotchas.md` — added "`--batch` +
  `--pinentry-mode loopback` are mutually exclusive on DECRYPT" and
  HARD INVARIANT "never pipe decrypted plaintext into agent context".
- **v1.3.0 (2026-07-05):** `templates/hermes-pass-install-recipe.md`
  — added "HARD INVARIANT: never ask the user to paste a secret
  value in chat by default" (user pushback 2026-07-05).
- **v1.2.0 (2026-07-02):** Refactored 36,471 to ~3KB body. Snapshot
  at `~/Downloads/refactor_2026-07-02/hermes-security-hardening_BACKUP.md`.

## `security` (renamed) changelog

- **v2.0.0 (2026-07-08):** RENAMED from `hermes-security-hardening`
  → `security`. Stripped the `hermes-` prefix per the user's
  "no prefix unless it disambiguates" rule. Body trimmed from
  20,042 → 14,857 bytes by:
  - Adding a consolidated threat-model + defenses table (was
    scattered across the body)
  - Moving the full version history to `references/CHANGELOG.md`
  - Pointer to the cross-profile write guard (now in `session`) and
    the chmod-600 rule (now in `session`) instead of duplicating
  Old skill dir soft-moved to
  `~/.hermes/skills/.archive/2026-07-08-consolidation/hermes-security-hardening/`.
  Content is byte-equivalent (the references/ subdir is a copy, not
  a rewrite). Triggered by user request: "Audit and consolidate
  these 6 skills" (2026-07-08).
