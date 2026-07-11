## SOUL.md is the identity slot — keep it universal, not project-specific (NEW 2026-06-27, this user correction)

SOUL.md is slot #1 in the system prompt. It's read every turn, cached, and multiplies by the number of turns in a long conversation. Two rules that govern what goes in:

**Rule 1: Universal only, not project-specific.** A SOUL.md rule that lives in EVERY profile (default + 5 specialists) should be a universal agent behavior — applies to every profile, every turn, regardless of project. Example rules that pass the test:
- Anti-duplicate-response: one tight response per tool batch, no re-drafting
- Scope-guard: verify file is in task scope before modifying
- Profile-island: profiles are flat, not hierarchical
- Secret-handling: leaked secrets get saved with chown 600 + rotation recommendation, never echoed

Example rules that FAIL the test (project preferences, not universal):
- Minimal-UI (single always-on element over toggles) — a project preference, not a universal agent behavior
- Obsidian write discipline — a workflow preference, not identity
- Webscraping via camofox — a task-specific gotcha, belongs in a skill or memory
- Token-bloat 2-stage router awareness — an implementation detail, not identity

**Rule 2: Trim jargon, don't add it.** Several anti-patterns to avoid:
- `You do NOT do: website copy/content (communicate-design), SD-merge theory (model-merger), general chat (default), experimental/throwaway (sandbox).` — REMOVE. The profile-router skill already handles routing. Repeating it in SOUL.md is a duplicate that goes stale.
- `(the field)` / `(the section this profile tells others to write)` / self-referential comments — cut filler after every sub-heading.
- `I do NOT do: ... → communicate-design` lists at the bottom of every profile — REMOVE all. The profile-router covers it.
- `Skills installed` sections listing every skill in the profile — cut. The skills catalog is auto-loaded; SOUL.md doesn't repeat it.
- `Sources to monitor` lists (r/PromptEngineering, arxiv cs.CL, etc.) — cut. Belong in a research skill, not the always-loaded identity slot.
- `Self-audit` date-stamped sections ("Before this turn: 1/10 ... After this turn: 7/10") — cut. Self-assessment is a one-shot, not a permanent identity.
- `Research artifacts` pointers to synthesis files — cut. The research lives at its own path; the agent can `read_file` it on demand.

**Target sizes after trim:**
- default: 4500-5500 bytes (was 5608)
- specialist profiles: 2500-4000 bytes each
- prompt-engineering specifically: under 4000 bytes (was 7560 — 50% trim)

**Universal trimming principle:** a SOUL.md that just repeats what the profile-router already says is a duplicate. Cut the duplicate. SOUL.md should be the *delta* — what makes THIS profile different from the others — not a restatement of the universal rules.
