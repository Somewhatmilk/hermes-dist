# Changelog — `routing` skill

## `profile-router` changelog (predecessor)

- **v2.0.3 (2026-07-03):** Cleaned up corrupted "Triggers" section.
  Added `adversary` as the canonical first trigger row, kept the rest
  of the list intact. Updated stale "5-profile architecture" history
  note to reflect the 7-profile count and the `reviewer` + `adversary`
  (renamed from `retrospect`) additions. Captured the user-established
  rule: "behavioral mode vs new profile" — persona roles (oppose,
  verify, simplify) live as personalities on existing profiles; new
  profiles are reserved for genuinely new fields of work.
- **v2.0.2 (2026-07-03):** Added verified "Personality overlays"
  section. Captured the verify-before-claim-CLI-features pitfall
  driven by user correction. Clarified that `/personality <name>`
  (per-chat overlay) and per-profile voice (SOUL.md + per-profile
  config) are independent mechanisms.
- **v2.0.1 (2026-07-02):** Added reference row pointing to new
  `per-project-context` skill (default-profile dispatcher wraps
  `mnemosyne_recall` with a project-scope confirmation step). Reason:
  user reported cross-project recall contamination in a 6-project
  parallel setup.
- **v2.0.0 (2026-07-02):** Refactored 50,586 to ~20KB body. Kept
  routing logic (sections 1-9) in body, moved 13 dated corrections
  and edge cases to `references/`. Snapshot at
  `~/Downloads/refactor_2026-07-02/profile-router_BACKUP.md`.

## `routing` (renamed) changelog

- **v3.0.0 (2026-07-08):** RENAMED from `profile-router` →
  `routing`. Stripped the `profile-router` prefix per the user's
  "no prefix unless it disambiguates" rule. Body trimmed from
  26,726 → 25,910 bytes by:
  - Moving the full version history to `references/CHANGELOG.md`
  - Updating the trigger table to current 7-profile state (added
    `reviewer` row, added `reviewer` column to the bigger-field
    test)
  - Fixing the inline profile count drift (5 → 6 → 7) in
    multiple places to be consistent with `hermes profile list`
    as of 2026-07-08
  Old skill dir soft-moved to
  `~/.hermes/skills/.archive/2026-07-08-consolidation/profile-router/`.
  Content is byte-equivalent (the references/ subdir is a copy, not
  a rewrite). Triggered by user request: "Audit and consolidate
  these 6 skills" (2026-07-08).
