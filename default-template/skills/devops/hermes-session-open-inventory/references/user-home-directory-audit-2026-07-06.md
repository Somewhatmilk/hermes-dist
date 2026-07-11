---
name: user-home-directory-audit
description: 5-tier classification of a Windows user home directory (C:\Users\<user>) when the user asks "what's in this dir?", "review this dir", "what's hermes vs orphan vs personal", "clean up my home dir", or "audit my install". Output is a markdown table with VERIFIED ACTIVE / VERIFIED INSTALLED-BUT-UNUSED / ORPHAN INSTALL / PERSONAL / UNKNOWN tiers, with one-line "what to do" for each row. Do NOT delete anything during the audit; the user confirms before any `rm`.
type: reference
applies_to: hermes-session-open-inventory
---

# User Home Directory Audit (5-tier classification)

Class of work: **the user asks you to review, audit, or classify the contents of a Windows user directory** (typically `C:\Users\<user>`, sometimes `C:\`, sometimes an arbitrary workspace). The deliverable is a structured markdown report — not a deletion, not a reorg, not a recommendation memo. The user is going to read the table and decide what to do.

This is a **mid-session audit**, not the session-open inventory. Different shape: it produces a classification table, not a "verified present/absent" list.

## When the user asks this

Trigger phrases:

- "review this dir", "what's in my home dir", "audit `C:\Users\somew`"
- "what's hermes vs orphan vs personal"
- "show me the layout of my install"
- "I want to clean up — give me a starting point"
- "what is `hermes/`, `hermes-research/`, `One-Cut-Deeper/`, etc."

Do NOT trigger on:

- Session start ("what's installed?") — that's `hermes-session-open-inventory`'s primary use
- "Is `llama.cpp` installed?" — single-tool probe, no classification needed
- "I want to delete X" — user has decided, just verify X is safe to delete

## The 5 tiers (output schema)

For every top-level entry under the audited dir, assign exactly one tier. The 5 tiers are:

| Tier | Definition | What the user should do |
|------|------------|--------------------------|
| **TIER 1 — VERIFIED ACTIVE** | This dir is in the active load path. Hermes reads/writes here this session OR a tool/skill you verified invokes it. | Keep. Document what writes here so cleanup later is informed. |
| **TIER 2 — VERIFIED INSTALLED, INACTIVE** | Files exist (binary, install dir, or config), but no tool in the live inventory references it. Could be: (a) installed but not used, (b) installed for a future use case, (c) the user forgot about it. | User decides. Common verdict: keep if it's a paid license, remove if it's a 4 GB never-opened game library. |
| **TIER 3 — ORPHAN INSTALL** | This is a known tool/application, but a SECOND copy / second version exists somewhere else and THIS one is the older one. Concrete test: same `Name` field from `Get-CimInstance` exists at two paths, OR a skill's path check returns TWO matches. | User can move to trash. Confirm the other copy is the one in use first. |
| **TIER 4 — PERSONAL** | Not Hermes / not a tool / not a project. The user's own content: photos, downloads, school/work, creative projects. | Leave alone. The user knows what's in here. Don't even ask "do you still need this" — they do. |
| **TIER 5 — UNKNOWN** | Cannot classify with current evidence. Either (a) the size probe timed out (huge / junction / loop), (b) the name doesn't match any known tool, (c) no source-of-truth file explains the dir. | User needs to look. Don't fabricate a tier. |

## The probe sequence (use `terminal()` not `execute_code`)

**Critical Windows caveat from `hermes-windows-filesystem-ops` philosophy #6:** `du -sh` and `find` with deep `-maxdepth` WILL HANG on a Windows user dir with OneDrive + Android SDK + junctions + symlinks. Always use bounded, timeout-wrapped commands.

```bash
# Step 1: top-level snapshot, fast (no recursion)
ls -la /c/Users/somew/ | head -50

# Step 2: per-entry metadata in one bounded pass
for d in $(ls -d /c/Users/somew/*/ 2>/dev/null); do
  name=$(basename "$d")
  # mtime of the dir itself (inception), not content
  inception=$(stat -c%y "$d" 2>/dev/null | cut -d. -f1)
  # file count under -maxdepth 2 (skips deep symlink loops, fast)
  count=$(find "$d" -maxdepth 2 -type f 2>/dev/null | wc -l)
  # size with HARD timeout — expect 2-5 to time out on a typical user dir
  size=$(timeout 3 du -sh "$d" 2>/dev/null | cut -f1)
  [ -z "$size" ] && size="TIMEOUT"
  printf "| %-30s | %-10s | %7s | %s |\n" "$name" "$inception" "$count" "$size"
done
```

**Expected output**: a table like:
```
| .android                      | 2024-08-15 |    1247 | 14G     |
| .hermes                       | 2026-07-06 |     312 | 4.2G    |
| .cursor                       | 2026-05-01 |      45 | 380M    |
| curseforge                    | 2025-11-22 |   12093 | TIMEOUT |
| ...
```

The `TIMEOUT` rows go to TIER 5 by default — they MIGHT be huge, but they might also be a junction loop. Don't try to force a size.

**Step 3 — evidence-based tier assignment.** For each row, the question is "does any tool or skill in the live inventory reference this path?" Run:

```bash
# A. Check active processes for this dir as CWD or path
for d in /c/Users/somew/*/; do
  name=$(basename "$d")
  # Find any running process whose CommandLine or CWD contains this name
  # (only feasible for ~10 dirs, not all 50)
  if [ "$name" = "hermes" ] || [ "$name" = ".hermes" ]; then
    echo "PROBE $name"
    timeout 5 powershell -NoProfile -Command \
      "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | \
       Where-Object { \$_.CommandLine -like '*${name}*' } | \
       Select-Object -First 3 ProcessId, CreationDate" 2>&1
  fi
done

# B. Grep all skill files for the dir name
grep -ril "/c/Users/somew/<suspect>" /c/Users/somew/.hermes/skills/ 2>/dev/null
grep -ril "/c/Users/somew/<suspect>" /c/Users/somew/.hermes/plugins/ 2>/dev/null
grep -ril "/c/Users/somew/<suspect>" /c/Users/somew/.hermes/cron/ 2>/dev/null

# C. Mnemosyne recall
hermes mnemosyne recall --query "<suspect-dir-name> install path" --limit 5
```

**A positive result from any of A/B/C → TIER 1 (verified active) or TIER 2 (installed, inactive).** Negative result + known-tool name → TIER 2/3 depending on whether a second copy exists. Negative result + unknown name → TIER 5. Match against `references/hermes-this-host-layout-2026-07-01.md` (this host's verified install) for fast yes/no on Hermes-related dirs.

**Step 4 — for TIER 3 (orphan) specifically: prove there's a SECOND copy in use.** A TIER 3 verdict requires:

```bash
# A. Find ALL copies of the tool on disk (not just this one)
find /c/Users/somew /c/Program* -maxdepth 5 -name "<tool>.exe" 2>/dev/null
# B. For each copy, check if any running process was launched from it
powershell -NoProfile -Command \
  "Get-CimInstance Win32_Process | \
   Where-Object { \$_.Path -like '*<tool>*' } | \
   Select-Object ProcessId, Path"
```

If TWO copies exist AND a running process came from the OTHER one, the audited dir is the orphan. **If only one copy exists**, it's TIER 2 (or TIER 1), not TIER 3 — there's no "other" to be orphaned by.

## Output format (the report)

A markdown table with one row per top-level entry, tier-banded:

```markdown
# C:\Users\somew\ — Audit Report (2026-07-06 16:48)

## TIER 1 — Verified Active (in load path this session)
| Path | Inception | Files | Size | What uses it | Action |
|------|-----------|-------|------|--------------|--------|
| `.hermes/` | 2026-05-28 | 312 | 4.2G | hermes CLI, all skills, Mnemosyne | Keep |

## TIER 2 — Installed, currently inactive
| Path | Inception | Files | Size | What it is | Action |
|------|-----------|-------|------|------------|--------|
| `cursor-resources/` | 2025-11-01 | 89 | 1.2G | Old Cursor IDE prompt archive | Move to trash if not using Cursor |

## TIER 3 — Orphan install (newer copy exists elsewhere)
| Path | Inception | Files | Size | Newer copy at | Action |
|------|-----------|-------|------|---------------|--------|
| `hermes/` | 2026-07-02 | 48 | 380M | `~/.hermes/hermes-agent/` (this one is the older sibling) | Move to trash |

## TIER 4 — Personal
| Path | Inception | Files | Size | Notes |
|------|-----------|-------|------|-------|
| `Documents/` | ... | ... | ... | School, taxes, etc. — left alone |
| `Downloads/` | ... | ... | ... | Standard download pile |
| `Pictures/` | ... | ... | ... | Photos — left alone |

## TIER 5 — Unknown (couldn't classify, needs user look)
| Path | Inception | Files | Size | Why unknown |
|------|-----------|-------|------|------------|
| `curseforge/` | 2025-11-22 | 12093 | TIMEOUT | Could be 20 GB mod archive, or junction loop. You know. |

## Summary
- **Keep**: 1 entry (`.hermes/`)
- **Review (your call)**: 2 entries (`cursor-resources/`, `hermes/`)
- **Leave alone**: ~25 entries (personal)
- **Need you to look**: 1 entry (`curseforge/`)
```

The "Action" column should NOT say "delete" — it should say "move to trash" or "review" or "keep". The user owns the deletion decision.

## The "don't volunteer structural advice" rule

**Do not** include a section like "## Recommendations" or "## Suggested Actions" that does the user's thinking for them. The audit is the deliverable. The user reads the table, runs through it, and decides. If they ask "what would you do?" AFTER the audit, answer that — but the audit report itself stays neutral.

Exception: if the audit reveals something actively dangerous (a credential stored in plaintext at a path that's world-readable, a binary in the autostart registry, a dangling symlink to a deleted network share), call that out with a ⚠️ symbol in a "Safety flags" section. That's not advice, that's a fact.

## Memory drift during the audit

During the audit you will likely discover the **canonical install path is NOT what memory claims**. Example: memory says research home is `C:\Users\somew\Documents\hemes-research\` (typo AND wrong), real is `C:\Users\<user>\.hermes\research\hermes-analysis\`. When this happens:

1. Note it in the report under "## Drift detected" — "memory said X, real is Y"
2. Update memory after the user confirms the report (one `mnemosyne_invalidate` on the old slot, one `mnemosyne_remember` with the new)
3. Do NOT update memory mid-audit — if the user wants the report abandoned or the audit re-scoped, you've already polluted memory with premature edits

## Example transcript (real, 2026-07-06)

User: "Setting it aside for now. Review this dir — see what's hermes, what could be archived or removed, what's personal — and we'll touch base."

Output: the 5-tier report above, ~25 rows in 5 bands, with one `hermes/` (TIER 3 orphan, older sibling of `~/.hermes/hermes-agent/`), one `~/.hermes/` (TIER 1), and a `curseforge/` (TIER 5 TIMEOUT).

User did not yet confirm. Audit is the deliverable; next step is user's call.

## Pitfalls

1. **Don't run `du -sh` on the audited dir itself.** Will hang. Always probe children with `timeout 3 du -sh <child>`. Treat exit 124 as TIMEOUT, not a size.
2. **Don't `find` deeper than `-maxdepth 2` per child.** A `find` with `-maxdepth 5` against a home dir WILL recurse into Android SDK (1M+ files), OneDrive cache, and a dozen junction targets. Each adds 10-30s. Use `-maxdepth 2` for the file count, and accept the small inaccuracy.
3. **Don't `rm` anything during the audit.** The audit is read-only. The user moves things; the agent never moves or deletes.
4. **Don't fabricate a tier because the name is "obvious".** `curseforge/` looks like a game mod tool — but it might also be a personal project named after the game. If the live probe returns nothing, it's TIER 5, not TIER 2.
5. **Don't classify based on the name alone.** `hermes/` (sibling of `.hermes/`) is the older orphan; classifying it as TIER 1 just because "hermes" is in the name would be wrong. The tier is set by the EVIDENCE, not the label.
6. **Don't include a "Recommendations" section.** The audit is the deliverable. The user decides.
7. **Don't update memory mid-audit.** Wait for the user to confirm the report.
8. **TIER 3 requires proof of a second copy in use.** One copy is not an orphan — it's just an install. The audit must show the OTHER copy is the one the running processes use, with evidence.
9. **On Windows, `stat -c%y` returns "no such file" for junction targets that have been deleted.** This looks like a missing dir; the entry is actually a dangling junction. Check `ls -la` for the junction arrow (e.g. `Downloads -> /c/Users/somew/OneDrive/Downloads` is a real path, but `stuff -> /c/oldserver/share` where the server is gone is dangling). Dangling junctions are TIER 5 with "dangling junction" in the Why column.
10. **PowerShell quoting from MSYS** (cross-ref `hermes-windows-filesystem-ops` philosophy #4): if you must use PowerShell to find a process path, write the script to a `.ps1` file and call with `powershell -File`, not `powershell -Command`. The `$_` in `Where-Object` gets eaten by MSYS dollar-quoting.
