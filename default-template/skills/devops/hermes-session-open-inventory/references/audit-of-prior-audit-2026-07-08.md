---
name: audit-of-prior-audit
description: 2026-07-08 worked example of catching two errors in a 2-day-old home audit (HOME_AUDIT_2026-07-06.md). Documents the prior-audit-TTL heuristic, the ~/.hermes/docs/-first precondition, the audit-must-produce-cleanup-batch rule, and the tmp<random>.env leaked-secret detection pattern. Companion to user-home-directory-audit-2026-07-06.md.
type: reference
applies_to: hermes-session-open-inventory
---

# Audit of a prior audit (2026-07-08)

Source session: 2026-07-08, this user. User asked "did u not review your own dir ~/.hermes yet there is multiple interesting folders" — the third narrow-scope failure in 14 days. The work was a re-audit of `~/.hermes/` against the 2026-07-06 audit (`HOME_AUDIT_2026-07-06.md` in `~/.hermes/docs/`). The 2026-07-06 audit had two load-bearing findings that turned out to be wrong; the live re-verification caught both.

## What I did wrong on the first pass (2026-07-08 morning)

User opened with the narrow-scope complaint. I started a fresh `~/.hermes/` walkthrough from memory. Concretely:

1. Ran `ls -la ~/.hermes/ | head -50` — saw the same shape as 2026-07-06.
2. Started reasoning about TIER 1/2/3/4/5 from scratch.
3. Did not `ls ~/.hermes/docs/` until prompted. Found `HOME_AUDIT_2026-07-06.md` with a date stamp of 2 days ago and **all the findings I was about to re-derive** (plus the 5-tier classification, plus the bounded Windows probe sequence, plus the orphan-alias pitfall).
4. **Realization:** the prior audit is the actual ground truth; the fresh walkthrough is duplicate work.

The user then asked me to *re-verify* the prior audit's specific findings live (this is the move that surfaced the two errors below). Without that prompt, the prior audit's wrong claims would have been re-asserted as if they were fresh findings.

## Two errors in the 2026-07-06 audit, both caught by live re-verification

### Error 1 — "Cron never fires" was wrong

The 2026-07-06 audit claimed: "6 cron jobs enabled, ZERO have ever fired." This was correct on 2026-07-06, but on 2026-07-08 the live state is:

| cron name | last_run_at | last_status |
|---|---|---|
| mnemosyne-curator | 2026-07-08 03:12 | ok |
| daily-mnemosyne-sleep | 2026-07-08 04:00 | ok |
| hermes-update-watchdog | 2026-07-07 21:30 | ok |
| weekly-knowledge-digest | 2026-07-06 02:00 | ok |
| intent-recall-demo | 2026-07-08 02:15 | ok (but silent no-op — see audit-of-prior-audit cron) |
| (other) | (other) | (other) |

**The scheduler was wired up between the two audits** (likely via a config change or restart around 2026-07-07). The 2026-07-06 audit was correct at the time; it's just stale now. **The lesson:** a "X never fires" claim from a prior audit is a snapshot, not a fact — re-verify before acting on it.

### Error 2 — "profiles/<name>/skills/ are auto-synced duplicates" was wrong

The 2026-07-06 audit claimed: "profiles/<name>/skills/ are likely auto-synced duplicates of `~/.hermes/skills/`" — implying they were full mirrors and could be safely pruned.

Live re-verification on 2026-07-08 with md5sum:

```bash
for prof in profiles/{adversary,reviewer,model-merger,communicate-design,software-engineering}/skills/; do
  for g in $(find ~/.hermes/skills -name SKILL.md); do
    skill_name=$(basename $(dirname "$g"))
    p="${prof}${skill_name}/SKILL.md"
    if [ -f "$p" ]; then
      if ! diff -q "$g" "$p" >/dev/null; then
        echo "DIVERGED: $p (profile copy differs from global)"
      fi
    else
      echo "FILTERED: ${prof}missing $skill_name (profile chose to exclude)"
    fi
  done
done
```

Output: **3 DIVERGED + 27 FILTERED per profile**, no byte-identical matches. The profile `skills/` is a **filtered curated override** (each profile picks which skills to load, with optional per-profile modifications), not a full mirror.

**Why the prior audit got this wrong:** the audit was run on a day when a `hermes skills list-modified` count was being tracked but the per-profile override mechanism wasn't surfaced in `hermes profile show`. Without that surface, the profile `skills/` dir looks like a duplicate of global. **The lesson:** for any "X is a duplicate of Y" claim, run `diff -q` (or `md5sum`) on at least a sample of the entries before acting. The 2026-07-06 audit did not do this step.

## Three new pitfalls this audit produced

These are now in the umbrella SKILL.md (Pitfalls #18, #19, #20). Restating them here with the worked example:

### #18 — Prior-audit-TTL

A prior audit's findings have a TTL. On a system that actively changes (cron state, recent skill creation), anything >2d old needs re-verification. The failure mode: "audit said X" → "agent acts on X" → "X was wrong, agent's actions are now wrong." Same class as Pitfall #11 ("user said we have X" is not "X is installed") — extend that pattern to the audit-author as a source.

### #19 — Audit-must-produce-cleanup-batch

The 2026-07-06 audit named 8 items as "safe to delete" (phantom locks, empty dirs, legacy `profile.yaml`) but produced no follow-through. They sat on disk for 2 more days, with a 22d-old `auth.lock` and 20d-old `kanban.db.init.lock` still there. The 5-tier classification table is necessary but not sufficient; the user needs a *do-this/drop-that* list. **The deliverable rule:** every audit closes with a proposed cleanup batch (move-to-trash list, with risk-tiering and rollback paths).

### #20 — `~/.hermes/docs/`-first

Before any `~/.hermes/` review, `ls ~/.hermes/docs/` and read what's there. The docs dir is the user's working memory of the install: prior audits, environment references, migration logs, secret-store patterns, retention policies. The 2026-07-08 audit was a 12-turn investigation that would have been a 3-turn read of `HOME_AUDIT_2026-07-06.md` followed by a 2-turn live re-verification.

## The `tmp<random>.env` leaked-secret pattern

While doing the 2026-07-08 re-audit, I found a `tmpnhii66cl.env` at `~/.hermes/` root. It was 25,798 bytes — within 0.4% of `~/.hermes/.env` (25,888 bytes). **This is a leaked temp copy of the real `.env`**, sitting in plain sight with a random tmpname. Likely cause: an editor that wrote a temp file during a save (vim, gVim, Notepad++) and the temp file was never cleaned up.

**Detection pattern (added to Pitfall #20):**

```bash
# Anything matching tmp*.env at ~/.hermes/ root is suspicious.
# Size check: if a tmp<random>.env has roughly the same size as
# ~/.hermes/.env (within 1%), it's a leaked copy.
ls -la ~/.hermes/tmp*.env 2>/dev/null
for f in ~/.hermes/tmp*.env; do
  [ -f "$f" ] || continue
  real_size=$(stat -c '%s' ~/.hermes/.env)
  tmp_size=$(stat -c '%s' "$f")
  diff=$(( real_size - tmp_size ))
  abs_diff=${diff#-}
  [ "$abs_diff" -lt $(( real_size / 100 )) ] && \
    echo "LEAKED COPY: $f (${tmp_size} bytes, real=${real_size})"
done
```

**Always flag the leak to the user with the file path, size, and a recommendation to shred (`sdelete -p 1 <path>` on Windows) rather than just `rm`** (plain delete leaves the bytes recoverable in the filesystem's slack space).

**Wider applicability:** the `tmp<random>` pattern is a class of leak — any temp file with secrets in it is a risk. Detection-by-name (`tmp*.env`) catches the most common case; a content-based scan (`grep -lE '(API_KEY|SECRET|TOKEN|PASSWORD)=' ~/.hermes/tmp*`) catches the rest.

## The deliverable this audit produced

Proposed cleanup batch (Tier A, B, C):

```
A. ZERO RISK (reversible via ~/.hermes/trash/):
   - tmpnhii66cl.env (leaked env copy, 25,798 bytes) — SHRED, do not rm
   - auth.lock (0B, 22d old — never re-populated)
   - kanban.db.dispatch.lock (0B, never re-populated)
   - kanban.db.init.lock (0B, 20d old)
   - image_cache/ (empty)
   - pairing/ (empty)
   - sandboxes/ (empty)

B. LOW RISK (verified-deleted by reading first):
   - profile.yaml (238B legacy format, predates profiles/<name>/config.yaml)

C. VERIFY FIRST (do not delete in this batch):
   - ~/.hermes/default/ (cloud-hosting-isolated-strict overlay, not a
     profile — verify nothing references it, then trash)
```

The user owns the deletion decision. The audit is the *evidence*; the cleanup batch is the *recommendation*; the user executes.

## Cross-references

- `references/user-home-directory-audit-2026-07-06.md` — the 5-tier classification scheme that the 2026-07-06 audit applied. Read first when doing any home audit.
- `references/cron-3-state-audit-2026-07-07.md` — the 4-state cron check that caught the silent no-op. Combined with this doc's "Cron never fires" was wrong, the two form the cron half of the prior-audit re-verification pattern.
- `hermes-profile-taxonomy` — the "Skills duplicated in profile overlay" section (v1.7.0) covers the byte-identical-mirror / user-modified / profile-only-stub trichotomy. **This 2026-07-08 finding refines it further: a fourth case exists — "filtered curated overrides"** — where the profile copy is a *subset* of global, not a full mirror or a divergence. The 2026-07-06 audit missed this case; `hermes-profile-taxonomy` should add it.

## Tics extracted

- User says "did you not review your own dir" / "you've been in this dir for hours" / "I just told you about X" — check `~/.hermes/docs/` and prior session_search hits FIRST. The agent is re-deriving something the user already documented.
- A "X never fires" or "X is a duplicate of Y" claim from any prior session — re-verify live with the relevant probe (`hermes cron list -v`, `diff -q`, `md5sum`) before acting. The 2-day TTL heuristic is a starting point; on actively-changing systems, even 1-day-old claims need re-verification.
- A `tmp*.env` or `*.env.bak` file at the root of `~/.hermes/` is almost always a leaked env copy. Run the size-match probe and flag the leak.
- "Did the audit produce a cleanup batch?" — if no, the audit is incomplete. The batch is the deliverable's close.
- User asks "do you recall X" / "didn't we do Y" / "I asked in a previous session" (NEW 2026-07-08) — that's a `session_search` query, NOT a `mnemosyne_recall` query. Mnemosyne is the index of *what the agent knows*; session_search is the index of *what was actually said*. Leading with Mnemosyne on an "event in a prior session" question produces a narrative built from a single high-importance summary, not the transcript — and the user will catch it within one turn with "are u not able to review the session or from the logs?". The discriminator: events → session_search first; stable facts → Mnemosyne first. Same English phrase ("do you recall X") can be either; the user's intent (event vs. fact) is the discriminator, not the words. See `references/recall-vs-session-search-2026-07-08.md` for the worked example.
