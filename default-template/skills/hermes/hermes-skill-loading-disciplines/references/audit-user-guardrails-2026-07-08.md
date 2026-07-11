# Audit/Consolidation User Guardrails — 2026-07-08, this user

The 9-point canon the user issued mid-audit when the agent presented a 16:52 plan's claims ("92K token/turn savings", "16-op batch approved") as established facts. Apply verbatim to any filesystem audit, skill consolidation, or bulk-delete work going forward. Pair with Pattern 13 (misleading-predecessor-canon) in `hermes-skill-loading-disciplines`.

## The 9 points (verbatim where possible)

1. **Token reduction is not the goal. Correctness and no lost information is the goal.** If a skill is 56K and that's what the domain requires, it stays 56K. Do not truncate or summarize to save tokens. Compress only by removing staleness, duplication, and dead references — never by cutting decision-critical detail.

2. **Source material must be preserved before deletion.** For any skill (or file) you archive or delete, first extract every unique fact, rule, trigger, CLI command, or workflow step that does not exist in the canonical version. Store extracted content in priority order:
   - **Mnemosyne** if it's a durable rule, preference, or design decision
   - **Obsidian** if it's reference material, research notes, or context a human needs for external review (write to the vault, not a skill dir)
   - **The canonical skill itself** if it's a missing trigger, edge case, or workflow variant that belongs in the active version
   - Do not delete an archived skill until you confirm the extracted content is stored and retrievable.

3. **Profile mirrors are out of scope.** The framework manages them. You manage only `~/.hermes/skills/` and its subdirectories. Do not touch profile-local copies.

4. **Archive is a staging buffer, not a home.** Read every archived skill. Extract anything still useful. Then delete. Same rule applies to your own `.archive/` moves.

5. **For skills with real content drift (size differs by >20%):** deep-read every pair. Do not decide canonical by size or mtime alone. The larger file is not always correct — sometimes it's bloated. The newer file is not always correct — sometimes it's a stub that replaced the real one. For each drift, return:
   - Which version is canonical and why (content comparison, not metadata)
   - What unique value exists in the non-canonical version
   - Where that value was stored (Mnemosyne, Obsidian, or merged into canonical)
   - Token delta after consolidation

6. **Hardcoded stale references — fix them.** Old skill names in `always_load`, dispatch maps, or cross-references must point to the new canonical names. No dead links. No references to archived skills unless the reference is historical and labeled as such.

7. **Dynamic and flexible over rigid.** After consolidation, skills should load on trigger, not sit in `always_load` unless they are turn-critical. The skill tree should survive you adding a new skill next week without breaking because a hardcoded list rotted.

8. **Do not batch decisions that need review.** For ambiguous cases (3 real variants of the same skill), present the content diff and your recommendation before acting. The user will confirm.

9. **Token tracking is informational, not a KPI.** Report deltas. Do not optimize for the number.

## What this canon changes about the agent's defaults

- **Default to "stage, not execute"** when the work is a multi-file audit/consolidate. Even if the user said "go ahead" earlier, if the batch is large (>5 files moved/deleted, or >50K total), stage the plan first, get a quick yes/no, then execute.
- **Default to "measure, not estimate"** when a prior number is involved. If the prior plan said "92K savings", measure it before the response. The cost is 1-2 tool calls. The cost of presenting an unmeasured number is the user's correction.
- **Default to "per-file decision"** when content drift is real. Never "the bigger file wins" or "the newer file wins." Read both, diff, decide, extract.
- **Default to "extract-first"** when deleting. Mnemosyne for rules, Obsidian for reference, canonical skill for in-scope content. Confirm the extraction is retrievable (recall it) before deleting the source.

## Worked example: the 2026-07-08 audit session

The 16:52 session proposed "Phase 4: execute all safe operations (no config.yaml or SOUL.md changes)." The next session lifted the proposed 16-op batch and started executing. The user stopped it with this canon. Following the canon would have meant:

- **Point 1**: "92K tokens/turn savings" is an estimate from raw byte/4. Real per-turn cost is closer to 30K (system prompt) + 3-10K (skill manifest). Savings is ~5-15K, not 92K. The plan was a ceiling, not a measurement.
- **Point 2**: before deleting the 7 archived skills, read each. 5 of 7 are confirmed byte-identical or back-ref-drift duplicates of canonical (safe to delete after extraction check). 2 of 7 contain unique content (~470K) that needs case-by-case extraction-or-merge.
- **Point 3**: profile mirrors are 8× copies of the canonical tree. Don't touch.
- **Point 5**: the 25 Pattern B drifts need deep-read. Sizes 67K / 56K / 10K on the same skill name don't auto-mean the 67K is canonical.

After applying the canon, the safe batch dropped from 16 ops to a staged plan: confirm each move with a measurement, read each unique file before deciding to delete or merge.

## The meta-lesson

The user gave this canon in a single mid-audit message. It's not a one-time correction. It's a class-level rule for any future agent doing filesystem audit, skill consolidation, bulk rename, or "cleanup" work. Encode it once in the skill, re-apply it every time the trigger fires.
