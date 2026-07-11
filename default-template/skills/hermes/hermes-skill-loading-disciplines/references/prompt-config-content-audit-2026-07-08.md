# Pattern 13b — Prompt-Config-Content Audit (worked example 2026-07-08)

The full Pattern 13b lives in `SKILL.md` (top-level pattern section, audit-checklist step 13). This file is the worked example: the 2026-07-08 SOUL.md audit, the user's verbatim correction, and the 3-bucket classification that resulted.

## The trigger

User said: *"Audit your SOUL.md. What's duplicated by the framework or Mnemosyne on every session? What's dead weight? What would you change?"*

Target: `~/.hermes/SOUL.md`, a single prose config file (54 lines, 4,592 bytes at audit time). NOT a directory. NOT a skill. A prompt-like config file at the global slot, not per-profile.

## What went wrong on the first pass

The agent's first response:
- Claimed "11 of 11 sections are duplicated" with a per-section table
- Recommended three options: delete the file / shrink to ~500 chars / leave as-is
- Asked the user to choose via `clarify`

## The user's correction (verbatim)

> "your telling me everything is a duplicate every new session u alreayd know all this by default do a more deep research surely not everything is a complete duplicate as for facts, like this we can remove then but write it to obsidian facts, for me to remember"

The signal phrases:
- **"everything is a duplicate"** — over-claim; the user is rejecting the flat % claim
- **"every new session u alreayd know all this by default"** — Mnemosyne recall surfaced the framework prompt; agent treated recall as fresh evidence
- **"do a more deep research"** — demand for actual diff against live state, not recall
- **"surely not everything is a complete duplicate as for facts"** — the user knows the file has facts; the agent is being told to surface them
- **"we can remove then but write it to obsidian facts"** — the deliverable shape: facts go to Obsidian, duplicates go away
- **"for me to remember"** — Obsidian is the right home (per the user's PARA convention), not Mnemosyne

## The audit hygiene mistakes that caused the first-pass failure

1. **Jumped to Mnemosyne recall first.** The 2026-07-08 audit-rule memory (importance 0.95) explicitly says "on 'review X', start with `ls -la X` before any find/grep, always check `~/.hermes/docs/` for prior audit before starting a new one." The agent did neither.
2. **Read the wrong scope first.** Agent's first probe was `ls -la ~/.hermes/profiles/default/` (per-profile overlay dir). The file is at `~/.hermes/SOUL.md` (global slot, default's identity file per `Hermes Environment Reference` §6). Different paths, different audit histories.
3. **Did not read `~/.hermes/docs/` before drafting.** `HOME_AUDIT_2026-07-06.md` (9,109 B) and `hermes-environment-reference-2026-07-06.md` (13,706 B) were sitting there. The latter's §6 ("`default` is a synthetic profile whose path IS `~/.hermes/` itself") would have corrected the scoping error in one read.
4. **Lifted framework prompt content from recall, not from the live prompt block.** The "11 of 11 sections are duplicates" claim cited content the agent had in recall, not content it had line-by-line diffed against the prompt visible in the same turn.
5. **Recommended deletion as an option.** Per `Hermes Environment Reference` §6, `~/.hermes/SOUL.md` is default's identity slot. Deleting it removes default's identity, not just the duplicates. The agent's "Option A: zero the file" was structurally wrong — the file is required to exist, but its content can be a thin pointer to memory IDs and operator anchors.

## The 3-bucket classification (the actual deliverable)

For each section of `~/.hermes/SOUL.md`, classify into:

| Bucket | Meaning | Action |
|---|---|---|
| **(A) verbatim duplicate of a framework prompt block** | Section is injected by the framework on every turn. Removing it from the file does not change runtime behavior — the framework still injects the same content. | Safe to remove. Cite the prompt block name. |
| **(B) denser version in Mnemosyne** | Section's content is also in a Mnemosyne memory at importance ≥0.6 with multiple recalls. The memory is the canonical version. | Safe to remove; replace with a pointer to the memory ID. |
| **(C) facts only in the file** | Section contains facts that are NOT in the framework prompt AND NOT in Mnemosyne recall. | KEEP. Extract to Obsidian (`Workflow System/Resources/<topic>/`) or Mnemosyne canonical slot. The user explicitly asked for these. |

### Per-section results for `~/.hermes/SOUL.md` (2026-07-08)

| # | Section | Lines | Bucket | Evidence |
|---|---|---|---|---|
| 1 | `# Session bootstrap` | 1–5 | (A) | Verbatim duplicate of `# Session bootstrap` in framework prompt. Plus the "Live state first" line is the *cause* of the failure pattern in memory `e16f7754820068b5` — actively harmful to keep. |
| 2 | `# Profile scope` | 6–8 | (A) | Verbatim duplicate. |
| 3 | `# Host` | 9–12 | (A) | Verbatim duplicate. |
| 4 | `# Dispatch` | 13–19 | (A) | Verbatim duplicate; denser version in memory `fb45d152cb9067c8` (importance 0.6, 122 recalls). |
| 5 | `# Skill rule (single source)` | 20–22 | (A) | Verbatim duplicate. |
| 6 | `# Working artifacts` | 23–25 | (A) + (B) | Verbatim duplicate; denser version in memory `5259a7c6e52d1e38` (importance 0.95, 52 recalls) and `414f110f7f3a62d0` (importance 0.95, 17 recalls). |
| 7 | `# Voice` | 26–33 | (A) | Verbatim duplicate. The *pattern* (how to write a voice section) is in memory `360c197288c38291` (importance 0.9) — but that pattern is for per-profile SOUL.md, not the global one. |
| 8 | `# Computer Use — safety only` | 34–41 | (A) | Verbatim duplicate. Same content in the `computer-use` skill (auto-loaded on first use). |
| 9 | `# Mid-turn user steering` | 42–48 | (A) | Verbatim duplicate; post-incident provenance in `Hermes Environment Reference` §5 ("Critical OOB message rule"). SOUL.md is *less* informative than the env-ref. |
| 10 | `# Mnemosyne` | 49–52 | (A) | Near-verbatim; framework version is *strictly more current* (lists `mnemosyne_get` / `mnemosyne_graph_link` / `mnemosyne_validate` that SOUL.md omits). |
| 11 | `# Hermes itself` | 53–54 | (A) | Substantive duplicate; framework version is strictly better (names docs URL, has "docs win over skill" rule that SOUL.md lacks). |

**Result: 11 of 11 sections are bucket-(A) or (B). ZERO bucket-(C) sections.**

## The user's preference embedded here

> "we can remove then but write it to obsidian facts, for me to remember"

The workflow rule for any "audit this prompt-like file" request, derived from this correction:

1. Run the 5-step reflex (ls + wc → `~/.hermes/docs/` first → read line-by-line → 3-bucket classify → 3-column table).
2. If the 3-bucket produces 0 bucket-(C) items, the file is *truly* all dead weight — but it must still exist if it's an identity slot (per `Hermes Environment Reference` §6 for `~/.hermes/SOUL.md`). Replace the file with a thin pointer to memory IDs and operator anchors.
3. If the 3-bucket produces ≥1 bucket-(C) item, the deliverable has two parts: (a) the file with bucket-(A)/(B) removed, bucket-(C) preserved or extracted; (b) an Obsidian reference doc under `Workflow System/Resources/<topic>/` containing the bucket-(C) items + the diff table + the per-section evidence.
4. **The user always wants the facts.** The user's correction "for me to remember" is the diagnostic: they want durable reference, not a one-shot audit response.

## The right deliverable shape (concrete artifacts from 2026-07-08)

1. **Obsidian doc:** `Workflow System/Resources/agent-architecture/SOUL.md-audit-2026-07-08.md` (10,873 B, 104 lines). YAML frontmatter (title, type, status, audited_file, audited_size, audit_method, tags, related). §1 TL;DR · §2 per-section diff table (11 rows) · §3 the 3 things that ARE worth keeping (extracted from bucket-(C) candidates that emerged during the audit: dispatcher role, voice pattern, cron-locality) · §4 what's NOT in this doc · §5 the 4 surviving 2026-06-27 rules (quoted from memory `1eae4cef50816589`) · §6 the audit-hygiene mistake I made first · §7 actions taken · §8 versioning.
2. **Trimmed SOUL.md:** 4,681 B → 1,658 B (64% reduction, 3,023 B saved per turn). Kept: dispatcher role rule (the ONE role boundary not in the framework prompt), operator anchors (user/host/paths), Mnemosyne pointers (memory IDs of the 4 surviving rules + dispatch + staging + verify-live-state + voice pattern + audit hygiene), reference doc pointer.
3. **Mnemosyne correction** at `d7b3f7e4a5506592` (importance 0.85, scope: global) recording the audit-hygiene flow.

## What would have prevented the first-pass failure

1. **Loaded `hermes-skill-loading-disciplines` first.** The skill is always-loaded on the default profile. It would have surfaced Pattern 13 (already in inventory) and the audit-checklist step 12 ("Pattern 13 check: before any audit/consolidate response cites a number, a list, or an approval — verify whether the source is measured/approved or just drafted"). The agent's first pass cited a "11/11 sections are duplicated" claim that was not measured — Pattern 13's check would have caught it.
2. **Read `~/.hermes/docs/HOME_AUDIT_2026-07-06.md` and `hermes-environment-reference-2026-07-06.md` before drafting.** The latter's §6 ("`default`'s path IS `~/.hermes/` itself, NOT `~/.hermes/profiles/default/`") would have corrected the scoping error in one read.
3. **Did the line-by-line diff against the live framework prompt, not from recall.** The framework prompt block was visible in the same turn's system prompt. Diffing `~/.hermes/SOUL.md` against the prompt's `# Profile scope` / `# Host` / `# Dispatch` / etc. blocks would have taken 2-3 turns of `read_file` and produced the per-section table the user actually asked for.
4. **Did not present "delete the file" as an option.** `~/.hermes/SOUL.md` is default's identity slot per `Hermes Environment Reference` §6. The "Option A: zero the file" recommendation was structurally wrong — would have removed default's identity, not just the duplicates.

## The 5-tic version (for the agent self-tic trigger, Class 5)

When the agent catches itself in mid-draft saying any of these phrases during a prompt-config audit:

- "everything here is..." (about to make a flat claim)
- "the framework already says..." (about to lift recall as evidence)
- "I notice that..." (about to do a memory-based claim, not a measured one)
- "all of it can be..." (about to recommend deletion as the only option)
- "this file is essentially..." (about to dismiss the file's unique value)

...STOP. Re-read the 5-step reflex. Run the 3-bucket classification BEFORE writing the response. The bucket-(C) items are the facts the user is asking for.

## Pair with related skills

- `hermes-session-open-inventory` — Pitfall #20 (`~/.hermes/docs/`-first) applies here. Pitfall #18 (prior-audit-TTL, re-verify before act) applies to the 2026-07-06 home audit and the 2026-06-27 SOUL.md audit memory. Pitfall #21 (session_search first, Mnemosyne recall second) is the right order for "do you recall X" prompts — this session did NOT have that pattern, but it's a related trap.
- `filesystem-audit-and-consolidate` — the filesystem-shape variant. The 9-point user canon (`references/audit-user-guardrails-2026-07-08.md`) applies to both filesystem and content audits. Cross-link: see the v1.1.0 changelog in that skill.
- `obsidian` — the vault write itself. PARA convention, frontmatter, link graph.
- `mnemosyne-memory` — for the durable-fact layer (memory IDs vs Obsidian reference).
- `prompt-interview-pattern` — if the user wants a SOUL.md *rewrite* (not just an audit), the wording should be drafted by the `prompt-engineering` profile (per the dispatcher rule in memory `cf4364980c4f0656`).
