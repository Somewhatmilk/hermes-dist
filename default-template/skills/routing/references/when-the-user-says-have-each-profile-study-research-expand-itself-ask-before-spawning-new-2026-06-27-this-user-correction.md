## When the user says "have each profile study / research / expand itself" — ask before spawning (NEW 2026-06-27, this user correction)

The user's literal request is "have each profile that isn't busy study, research, discover new tools, skills, information to expand their current role and system prompt." The wrong move is to spawn N parallel subagents with vague goals and let them auto-merge into SOUL. Real failure modes:

- **Auto-merge drift.** A self-directed LLM loop with no ground truth tends to grow SOUL.md into a mess of half-digested tips. The 2026-06-27 SOUL-trim memory documented 50% trim on prompt-engineering because the auto-grown SOUL was duplicating profile-router, listing skills already auto-loaded, and bloating with date-stamped self-assessments.
- **Vague scope → vague output.** "Study X" produces a 1-page survey that doesn't tell you what to change. "Find 3 concrete gaps and propose 1 specific tool/skill" produces something you can review.
- **Cost blind spot.** Each profile in this setup is `MiniMax-M3` via the user's custom provider. 5 profiles × "research until you have a proposal" = real tokens. The user said "while your at" — that wasn't authorization to spend whatever it takes.

**The question set to ask before running a research pass across profiles** (5 questions, not 6 — discovered the right shape this session):

1. **Scope per profile** — pick one:
   - (A) **Skim only** — each profile reads its own SOUL + MEMORY + last 3 closed tasks, writes a 1-page "what's already here, what's clearly missing." No web. ~2 min each.
   - (B) **Skim + targeted research** — (A) plus 1–2 web searches inside the profile's domain, with 1–2 proposed tool/skill additions per profile, each cited. ~5–10 min each.
   - (C) **Skim + research + propose SOUL edits** — (B) plus each profile proposes a concrete SOUL.md patch.
   - **My default recommendation:** B for the first pass, then escalate to C for selected profiles based on B's output.
2. **Budget** — explicit cap (e.g. "30 min total" or "stop after each profile writes its proposal"). "Until you run out" is not a budget.
3. **Output destination** — kanban tickets on each profile's own board, markdown files under `~/.hermes/profiles/<name>/research/`, or gateway chat posts. Default: kanban tickets, you review like any other work.
4. **Auto-merge vs. review** — should proposals be auto-applied to SOUL.md/skills/, or do you approve each one first? **Strong default: never auto-merge.** SOUL edits are reviewed. Skill creation goes through the standard `skill_manage` flow.
5. **Which profiles + scheduler** — which profiles are in scope, and is this a one-shot or a recurring cron (e.g. "Sunday 3am weekly research hour")?

**The pattern is also in `hermes-subagent-dispatch-decisions` for "when to fan out"** — but the rule of thumb is: if the user said "do X for each profile," the answer is *not* "OK I'll spawn now," it's "OK I'll ask 5 questions, then spawn." Spawning-without-scope is the dispatch version of over-investigation.
