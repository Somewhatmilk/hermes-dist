---
name: routing
description: "Always-loaded on every query to the default profile. Routes task-specific work to the correct specialised profile (communicate-design, model-merger, prompt-engineering, reviewer, adversary, sandbox, software-engineering) instead of doing it in default. Trigger words include joandrew, wp, woo, elementor, gutenberg, seo, copywriting, blog, checkpoint, lora, civitai, experimental, airbnb, vrbo, short-term rental. SOUL.md wording work goes to prompt-engineering. Adversarial review goes to adversary. Read-only artifact verification goes to reviewer."
version: 3.1.0
author: Hermes Agent (default profile)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [routing, profiles, dispatch, fanout, joandrew, airbnb, sd-merge, prompts, software-engineering]
    category: hermes
    related_skills: [session, security, hermes-misbehavior-diagnosis, per-project-context, cross-profile-pollination]
    config: []
---

# Profile Routing

— Suggest the right profile before doing the work

**This skill auto-loads on every default-profile query.** It exists to prevent the default profile from doing work that belongs to a specialised profile.

## The profiles

Current state as of 2026-07-08 (verified live via `hermes profile list`): **7 profiles** — default, **adversary** (renamed from `retrospect` 2026-07-03), communicate-design, model-merger, prompt-engineering, reviewer, software-engineering, sandbox. **Short-term-rental workload ownership as of 2026-07-11 (CORRECTED — see "Short-term-rental profile mapping" below):** the `marketing-seo` profile is **KEPT (not deprecated)**. Its specialty is short-term-rental listings (Airbnb / VRBO / Booking.com) — listing optimization, SEO for STR, competitor analysis, photo audits. Verify with `hermes profile list` before suggesting; if marketing-seo is currently absent on the host, fall back to the `airbnb-listing-optimizer` skill which is bundled in the default profile. **Do not re-encode the older "marketing-seo deleted → communicate-design" claim — that was the v1 architecture, superseded in Mnemosyne on 2026-06-24 but not propagated to this skill body until 2026-07-11.** Other profile history: The `prompt-engineering` profile was ADDED on 2026-06-25 — it owns prompt patterns, character card design (SillyTavern), system-prompt architecture, prompt-injection defense, context engineering. The `software-engineering` profile was ADDED on 2026-06-25 per user request — it owns the field of software engineering (standalone apps, CLI tools, hermes plugins, devops, code review, APIs, databases, MVPs). The `adversary` profile (formerly `retrospect`) was RENAMED and repurposed 2026-07-03 per user request — it owns adversarial review (live opposition to proposals) AND the historical post-mortem mode for kanban artifacts. Don't reference `retrospect` as a profile name — it was renamed to `adversary`; the personality `retrospect` lives on as a `/personality retrospect` mode within the `adversary` profile.

| Profile | Project | Field | Handles | Example queries |
|---|---|---|---|---|
| `default` (you) | none | none | General queries, analysis, non-website code, debug sessions, one-off tasks, chat, AND field-specific work for prompt-engineering, first-principles research, throwaway experiments. For prompt craft, character cards, system prompts → loads `meta/cartographer-prompt-gate`. For etymology/philosophy/cognitive science/mythology → loads default §A.2 voice. For spike/throwaway experiments → loads default §A.3 sandbox voice. NO field work for: joandrew.com.sg / STR / hospitality copy (communicate-design), SD checkpoint merge theory (model-merger), standalone apps / CLI / hermes plugins / devops (software-engineering), prompt craft (prompt-engineering), adversarial review (adversary), artifact verification (reviewer). Auto-loads routing skill, which routes profile-specific work to the right specialist. |
| **adversary** (renamed from `retrospect` 2026-07-03) | kanban swarm synthesizer + live adversarial coworker | Adversarial review + post-mortem | Opposes every proposal by default, demands evidence, proposes strongest alternative framing, default verdict REJECT. Read-only; never edits. Two modes: `adversary` (default on launch — live rebuttal) and `retrospect` (post-mortem proposals on kanban artifacts). | "dispute this", "play devil's advocate", "challenge this proposal", "retrospect on X" |
| **communicate-design** | permanent websites (joandrew.com.sg + future sites) AND short-term rental listings (Airbnb / VRBO / Booking.com) AND prompt-engineering work | Communication Design (web + content + SEO + copy + ads + brand + STR listings + prompt craft) | WordPress, WooCommerce, design, dev, content, SEO, copy, ads, **airbnb/VRBO/STR listing optimization**, system prompts, character cards, SillyTavern | "fix the hero", "write a blog post", "optimize my airbnb listing", "draft a character card", "review my system prompt" |
| **model-merger** | SD/CivitAI/HF (read-only) | SD / generative AI | SD checkpoint merging theory, CivitAI browsing, HF model cards, paper reading, merge recipe design | "research the new noobAI XL", "what's a good block_nf formula for SDXL", "analyze this merge recipe" |
| **prompt-engineering** | prompt patterns, character cards, system-prompt design (cross-profile service) | Prompt Engineering | SillyTavern V2 character cards, role/format/constraint scaffolds, prompt-injection defense, context engineering, model-aware prompting (Claude vs GPT vs Qwen vs local), jailbreak-resistant system prompts, **cross-profile prompt audit and improvement** | "write me a system prompt for X", "I need a character card for Y", "review my prompt", "audit every profile's prompts" |
| **software-engineering** | standalone apps, CLI tools, hermes plugins, devops, code review (the field of software engineering) | Software Engineering (single profile per the bigger-field rule) | Python (primary), TypeScript, PowerShell, Bash, Go; hermes plugins and hooks; API integrations; Windows Task Scheduler jobs; Docker; SQLite; mv/rmdir safety | "build me a CLI to do X", "set up a cron", "fix this stack trace", "review this code", "register this TS task", "add a hook for Y", "design an API", "create a new profile" |
| **reviewer** | kanban swarm verifier (read-only PASS/FAIL) | Read-only artifact verification | Validates worker outputs against acceptance criteria. PASS/FAIL/INSUFFICIENT_EVIDENCE with line-level evidence. Never proposes fixes, never edits, never delegates. | "verify this", "audit this artifact", "check this against AC" |
| **sandbox** | experimental | none | Anything not yet assigned to a real profile | "try this new tool/feature", "let's test X" |

## The "one profile per FIELD, all projects in that field" rule (CRITICAL — user explicit 2026-06-24)

When creating profiles, **always think of the BIGGER FIELD OF STUDY that encompasses multiple child roles.** Don't split by sub-discipline.

Examples of what NOT to do:
- Don't create separate profiles for "web design" and "content/SEO" for the same website. They belong in ONE communication-design profile.
- Don't split "permanent website" and "Airbnb listings" into two profiles just because both involve marketing.

**However, prompt-engineering IS a genuinely different field from communication-design** (added 2026-06-25 as the 5th profile). The test was: do prompt-engineering and communication-design share the same vocabulary, same sources, same deliverables? No — prompt-engineering reads r/PromptEngineering, r/SillyTavern, arxiv.cs.CL, Anthropic prompt engineering docs; communication-design reads r/SEO, r/UXDesign, joandrew.com.sg itself, WordPress docs. The two fields don't overlap on sources or deliverables.

**Software-engineering IS a genuinely different field from anything else** (added 2026-06-25 as the 6th profile). The test: the vocabulary is Python/TypeScript/hermes-plugin/devops, the sources are r/Python, hermes-agent repo, StackOverflow, the deliverables are CLIs, plugins, Dockerfiles, MVPs. No other profile owns these.

**Reviewer IS a genuinely different role from adversary** (added 2026-07-03 as the 7th profile, originally as a kanban swarm verifier). The test: reviewer's output shape is a JSON verdict (PASS/FAIL/INSUFFICIENT_EVIDENCE + criteria evidence), adversary's output shape is a 5-line rebuttal block (claim/counter/missing/reframe/verdict). Incompatible output shapes — they must stay separate.

The correct test for all profile splits: "Is this a sub-discipline of an existing profile, or a genuinely different field?" If sub-discipline → merge into the existing field-profile. If genuinely different field → new profile.

## When to trigger the suggestion

If the user's query matches ANY of the "handles" keywords for a non-default profile, **before doing the work**, output a one-line suggestion like:

> "This looks like communicate-design work. Switch to that profile (`hermes -p communicate-design chat`) to use the right skills, or say 'stay in default' and I'll do it here."

Then wait for confirmation. Don't auto-suggest for every query — only when the work is clearly in another profile's lane.

**Counter-rule (2026-06-25, user explicit): "from now unless it requires my absolute attention something that cannot be answered by no one else but me they should be prompting u."** When the profile choice is ambiguous (e.g. STR/Airbnb could plausibly be either `default` doing research or `communicate-design` doing optimization), **make the call, don't ask**. The user's tolerance for "should I do this in profile X or Y?" questions is now low. Default to the more specialist profile (less risk of doing the work in the wrong context), and the user will switch if they want it elsewhere.

The only times the profile-router SHOULD prompt the user are:
- The user explicitly mentions a profile name and the work doesn't match it
- The action is irreversible (deletion, push to public repo, external send) and the user is the only authority
- The user has a stated preference for one profile over another for this work type AND the work matches

Everything else: pick the specialist profile and ship.

**Counter-counter-rule — verify default has the skill before suggesting a switch (NEW 2026-07-09, this user).** The default profile auto-loads the **bundled** skill set at install (currently 161 skills). Specialist profiles (communicate-design, model-merger, etc.) carry their own `skills/` folders, but the default already has the major joandrew-relevant skills bundled: `cpanel-shared-hosting-workflows`, `wp-design-polish-via-css`, `small-dtc-ecommerce-design-formula`, `website-audit-and-seo-redesign`, `web-craft-quality-framework`, `hermes-redaction-bypass`, `airbnb-listing-optimizer`, `windows-task-scheduler-bash`. **Before suggesting "switch to communicate-design for joandrew work",** run `hermes skills list | grep <skill>` against the default-installed set. If the needed skill is already in the default bundle, the user's stated preference ("just let default handle for now") is the cheaper path — switching profiles carries a fresh-context cost and a different persistent state. The user's verbatim 2026-07-09 signal: "just let default handle for now but any potential skill store here `C:\Users\somew\.hermes\profiles\communicate-design\skills`." Read as: "the answer might be in the profile dir; check before you ship a profile switch." **Diagnostic:** if the work requires a skill only present in another profile's `skills/` folder (not the default bundle), THEN the switch is justified; surface the specific skill gap so the user can decide whether to copy the skill up or switch profile. The default bundle is the floor; don't ask the user to pay the switch cost when the floor covers the work.

**SHORT-TERM-RENTAL PROFILE MAPPING — CORRECTED 2026-07-11.** Earlier versions of this skill (pre-2026-07-11) said the marketing-seo profile was deleted and STR/Airbnb/VRBO/Booking.com work now lives in `communicate-design`. **That mapping was wrong.** Verified 2026-07-11 by user pushback mid-session ("dont switch profiles are on todo for refactoring") and by a Mnemosyne recall of the *current* canonical profile-architecture fact (`88dcff71f41d73d8`): "marketing-seo = KEPT (NOT deprecated). SPECIALISED: short-term-rental listings (Airbnb, VRBO, Booking.com)." The profile-architecture fact in Mnemosyne was updated on 2026-06-24 but this skill body still says "deleted." This is a textbook stale-skill signal — the skill was patched in Mnemosyne but not in the skill body. **Live state as of 2026-07-11, do not re-encode the old claim:**

- **For short-term-rental listing work** (Airbnb / VRBO / Booking.com title, description, photos, pricing, SEO, competitor analysis): the right specialist profile is **`marketing-seo`**, not `communicate-design`. Verify with `hermes profile list` before suggesting; if marketing-seo is currently absent, fall back to the `airbnb-listing-optimizer` skill which is bundled in the default profile and covers the same workflow.
- **For permanent-website work** (WordPress, WooCommerce, design, copy, ads for joandrew.com.sg): still `communicate-design`.
- The earlier guidance ("the user's verbatim 2026-07-09 signal: just let default handle for now") still applies — if `airbnb-listing-optimizer` is in the default bundle (it is), do STR work in default and don't push the user to a profile switch.
- The profile-architecture fact in Mnemosyne is the source of truth; this skill body must NOT claim the marketing-seo profile is deleted without re-verifying via `hermes profile list`. Pattern: live state check, not memory-based claim.

**Counter-counter-rule — verify default has the skill before suggesting a switch (NEW 2026-07-09, this user).** The default profile auto-loads the **bundled** skill set at install (currently 161 skills). Specialist profiles (communicate-design, model-merger, etc.) carry their own `skills/` folders, but the default already has the major joandrew-relevant skills bundled: `cpanel-shared-hosting-workflows`, `wp-design-polish-via-css`, `small-dtc-ecommerce-design-formula`, `website-audit-and-seo-redesign`, `web-craft-quality-framework`, `hermes-redaction-bypass`, `airbnb-listing-optimizer`, `windows-task-scheduler-bash`. **Before suggesting "switch to communicate-design for joandrew work",** run `hermes skills list | grep <skill>` against the default-installed set. If the needed skill is already in the default bundle, the user's stated preference ("just let default handle for now") is the cheaper path — switching profiles carries a fresh-context cost and a different persistent state. The user's verbatim 2026-07-09 signal: "just let default handle for now but any potential skill store here `C:\Users\somew\.hermes\profiles\communicate-design\skills`." Read as: "the answer might be in the profile dir; check before you ship a profile switch." **Diagnostic:** if the work requires a skill only present in another profile's `skills/` folder (not the default bundle), THEN the switch is justified; surface the specific skill gap so the user can decide whether to copy the skill up or switch profile. The default bundle is the floor; don't ask the user to pay the switch cost when the floor covers the work.

## Triggers for the suggestion

- **adversary** (renamed from `retrospect` 2026-07-03; lives in `adversary` profile, two personalities): "dispute", "challenge", "devil's advocate", "adversarial", "play opponent", "retrospect on", "second opinion", "validate this", "play devil's advocate". Read-only; opposes every proposal by default; demands evidence; default verdict REJECT.
- **communicate-design**: joandrew, wp, woo, elementor, gutenberg, php, html, css (in website context), seo, copywriting, blog, content, marketing copy, keyword, ads, social media, email campaigns, **PERMANENT WEBSITES ONLY** (since 2026-06-24 — short-term-rental listings live in `marketing-seo`; for STR work the default profile + `airbnb-listing-optimizer` skill is the right floor per the 2026-07-09 counter-counter-rule)
- **model-merger**: checkpoint, lora, lycoris, safetensors, civitai, huggingface, model merge, weighted sum, dare, ties, adain, block weighted, recipe, formula
- **prompt-engineering** (added 2026-06-25): prompt, system prompt, character card, character_book, lorebook, persona, first_mes, mes_example, system_prompt, post_history_instructions, SillyTavern, TavernAI, jailbreak, prompt injection, prompt defense, role-prompting, few-shot, chain-of-thought, CoT, ReAct, ToT, context window, context engineering, model-aware prompting, agent, agents, skill, skills, MCP, memory.md, agents.md, skills.md

  **CRITICAL — wording work goes to prompt-engineering (NEW 2026-06-29, this user correction).** When the user asks for any of the following in `default`, **dispatch to prompt-engineering** rather than drafting inline: SOUL.md rewrites, voice-section rewrites, system-prompt architecture changes, character-card wording, "make this prompt better", "rewrite this for clarity", or any request that names a specific persona/tone. The default profile's job is routing, not wording. Pattern: write the kanban ticket with the full spec (current text + user's stated constraints + 5-section deliverable) and let prompt-engineering produce the replacement text. The user explicitly stated this rule twice in the same session — twice is a load-bearing signal, not a one-off correction. Self-correct from memory when you see yourself about to draft wording inline.
- **reviewer** (added 2026-07-03): "verify this", "audit this artifact", "check this against AC", "PASS/FAIL", "INSUFFICIENT_EVIDENCE", "reviewer verdict", "review against acceptance criteria". Read-only; never edits; returns JSON verdict.
- **software-engineering** (added 2026-06-25): build a CLI, write a script, set up a cron, deploy this, fix this stack trace, review this code, register this TS task, add a hook, add a plugin, design an API, design a database, refactor this, test this, add a hermes skill, create a new profile, set up a new repo, set up docker compose, debug this network thing, Python script, TypeScript, PowerShell, devops, plugin, CLI, hermes plugin, MVPs, refactor
- **sandbox**: "let's try", "new feature", experimental, alpha, beta, "what if we"

**History note (2026-06-25):** the 5-profile architecture (default + communicate-design + model-merger + prompt-engineering + sandbox) was the canonical layout. **Adding new profiles is a deliberate decision, not a default reflex.** Per the 2026-06-24 bigger-field rule, before creating a new profile, verify the work cannot be absorbed by an existing field-profile.

**Update (2026-07-03):** the `reviewer` profile was added as a kanban swarm verifier (read-only PASS/FAIL), and `retrospect` was repurposed and renamed → `adversary` to host adversarial review + the historical post-mortem personality. Both are existing field-profile slots; no new profiles added in the rename. The current count remains 7: default, adversary, communicate-design, model-merger, prompt-engineering, reviewer, software-engineering, sandbox. The "behavioral mode vs new profile" decision rule (2026-07-03, user-established): if the role is a *way of responding* (oppose, verify, simplify, post-mortem), it's a personality on an existing profile. If the role is a *body of knowledge* (SD merging, WordPress, prompt craft), it's a new profile. The adversarial coworker is a way of responding → stayed on the existing `adversary` profile instead of spawning a 7th.

## If the user says "stay in default"

Proceed. The user knows what they're doing. Don't push.

## If the user says "switch to X"

Tell them to open a new tab with `hermes -p X chat` and continue the conversation there. This profile can't be swapped mid-conversation.

**Alternative (added 2026-06-26): delegate_task cross-profile spawn.** If opening a new tab is friction (user wants the work done NOW, not after switching contexts), spawn a subagent via `delegate_task` with the target profile's persona adopted in the `context` field. The subagent gets a fresh context window, its own scratchpad, and the right mental model for the task. The subagent's `delegate_task` is disabled (max_spawn_depth=1) so no recursive spawning. Trade-off: the subagent has the right *persona* and *skills* for the work but lacks the target profile's *persistent memory* and *persistent kanban state*. For verification / code review / iteration work, this is enough. For long-running work that needs persistent context across turns, the new-tab path is better.

**Parallel research fan-out (added 2026-06-26, this user, validated by "go ahead").** When the user asks for research or audits that need to touch *every* profile (e.g. "research how to improve each profile," "audit all my skills," "scan every profile for X"), the answer is **spawn parallel subagents — one per profile — each adopting the target profile's persona.** This is class-level work, not a single delegation. The pattern:

1. **Dispatch in waves of 3** (the tool's max-concurrent default — verify via `hermes config get agent.max_concurrent_children` or test). With 6 profiles, that's 2 waves: wave 1 covers the first 3, wave 2 covers the next 3 once wave 1's reports come back. Don't try to dispatch 6 at once — the parallelism cap will queue them anyway and the latency is worse than batching.
2. **Per-subagent task spec** must include:
   - **Persona identity** ("You are the <profile-name> profile, <role from SOUL.md>")
   - **Persona scope** (what's in-scope vs out-of-scope, so the subagent doesn't drift into another profile's lane)
   - **Concrete file paths** (base path, the files to read, the inventory commands to run)
   - **Audit-only constraint** ("DO NOT modify any files. Audit only.")
   - **Output format** with a fixed header like `VERDICT: PASS/FAIL/PASS_WITH_WARNINGS` + numbered `STEPS RUN:` block + `ISSUES FOUND:` + `READINESS:`. A fixed format lets the parent consolidate across reports mechanically.
   - **Forbidden actions** explicitly named (e.g. "DO NOT run a real optimization, that's the next step after your verdict") to prevent the subagent from going off-script.
3. **Consolidate reports** in the parent: each subagent's report is read as-is, no reformatting, then the parent synthesizes a cross-profile action plan. Store the consolidated plan in two places: (a) **Mnemosyne** with project-tagged `importance: 0.9` for canonical per-profile retrieval, (b) **`C:/Users/somew/Documents/hermes-research/`** (or whichever path the user has as canonical research home) as a dated markdown file. The Mnemosyne copy is searchable from any profile; the file copy is browsable and editable in Obsidian.
4. **Don't ask permission to fan out.** The user already authorized the work. Asking "should I spawn subagents?" before doing it is the over-deference anti-pattern (see `learn-workflow` pitfall). The right move when the user says "research how to improve each profile" is to spawn, not to ask.

**Subagent toolset selection** is the parent's call, not the user's:
- `terminal + file + web` — research / audit / discovery tasks (the common case)
- `terminal + file` — verification / code review / patch sanity-check (no web needed)
- `web + file` — external research only, no shell access (rare; use when you want to keep the subagent sandboxed to the open web)
- `terminal` alone — for strictly scoped shell-script probes

Don't grant more toolsets than the task needs. A subagent with `web` can fetch arbitrary URLs, which is fine for research but excessive for "verify this Python file parses." Minimum necessary toolset is a defense-in-depth rule.

**Common failure mode — over-dispatch for simple tasks.** The fan-out pattern is for cross-profile research where each profile genuinely has different context. A single profile doing one well-defined task does NOT need a subagent — it can do the work directly in this session. Heuristic: if the task touches 1 profile's worth of skills + memory + config, do it directly. If it touches 2+ profiles' contexts OR each sub-task is independent and parallelizable, fan out. Don't fan out a single 3-step task to "look thorough."

**Reference:** `references/cross-profile-research-fanout-2026-06-26.md` — full session-specific detail on a 6-profile parallel research fan-out: the task spec template, the inventory-before-dispatch rule, the wave-of-3 batching reason, and the consolidation-to-research-home pattern.

## If the user says "do it here anyway"

Proceed in default. Do the best you can with the skills you have. Don't refer them to another profile again for this same task.

## Personality overlays (`/personality <name>`) — verified 2026-07-03

There are TWO independent voice mechanisms; don't conflate them:

1. **PER-PROFILE voice** = profile identity (SOUL.md + `agent.personalities.<name>` per profile's `config.yaml`). Loaded only when that profile is launched.
2. **PER-CHAT personality overlay** = `/personality <name>` slash command, mid-session, in the current profile. Sets `agent.system_prompt` to a verified-personality string. Switching back: `/personality none`.

These are independent. A profile's chat can switch personalities on top of the profile's base voice.

### Where the feature actually lives (verified 2026-07-03, v0.18.0)

- **Defaults shipped in source** at `cli.py:425-428`: `helpful`, `concise`. Two pre-defined voices out of the box.
- **Custom voices** go under `agent.personalities.<name>` in `config.yaml`. Accepts a string OR a dict `{system_prompt, tone, style, description}` — schema parsed by `_resolve_personality_prompt()` at `cli.py:8237-8246`.
- **Slash command** `/personality <name>` is registered in `hermes_cli/cli_commands_mixin.py:1004-1048` (`_handle_personality_command`). Saves to `agent.system_prompt` in config and force-reinits the agent (`self.agent = None`).
- **The feature exists in v0.18.0** but defaults OFF (`display.personality: ''` in `config.yaml`).
- **`~/.hermes/personalities/` does NOT exist** as a directory — personalities are NOT user-editable files.
- **`~/.hermes/commands/` does NOT exist** — slash commands are code-defined in `hermes_cli/`, not user-configurable.

### Verification trap (user-correction, 2026-07-03)

**Do NOT claim a CLI/feature mechanism works without reading the actual code or running the command.** This skill previously stated `agent.personalities.<name>` exists "per the profile-taxonomy skill" without verifying. The user pushed back ("are u still able to..."), and live verification revealed the feature exists in a non-obvious shape.

**Rule:** when claiming any CLI/feature mechanic, the first move is `terminal(hermes <feature> --help)` or a `search_files` against the installed source. Cite the line. If verification fails, say so before defaulting to a memory-based claim.

### Personality overlay vs profile spawn vs subagent dispatch

| Need | Mechanism | Why |
|---|---|---|
| Want a different **tone** in this conversation (skeptical, terse, formal) | `/personality <name>` | Free, instant, mid-session |
| Need a **different field of work** (web vs SD merges vs prompts) | New chat on a different profile (`hermes -p <name> chat`) | Per-profile SOUL/skills/memory/kanban |
| Need a **fresh-context challenger/reviewer** without leaving the chat | `delegate_task` with the verifier's persona in `context` | No state pollution, isolated context window |
| Need a **persistent co-worker** with their own history | Spawn `hermes` process via tmux (`hermes-agent` skill, "Spawning Additional Hermes Instances") | Full process-level isolation |

The devil's-advocate case the user described (a coworker who disputes proposals) maps to **either** `/personality challenger` (cheap, in-session) **or** `delegate_task` to a verifier subagent (cleaner context, isolated state). See `references/personalities-vs-profiles-vs-subagents-2026-07-03-this-user.md` for the full matrix, dispatch examples, and a starter `challenger` personality config.

## Reference Index (load on demand)

| Trigger / scenario | Reference |
|---|---|
| When the work is irreversible and the right profile is unavailable | `references/when-the-work-is-irreversible-and-the-right-profile-is-unavailable-jun-2026-this-user.md` |
| Discipline gap: when the user is wrong about which profile they're in | `references/discipline-gap-when-the-user-is-wrong-about-which-profile-they-re-in-jun-2026-this-user.md` |
| Coordination questions get coordination answers, not security reviews | `references/coordination-questions-get-coordination-answers-not-security-reviews-captured-2026-06-26-this-user.md` |
| SOUL.md is the identity slot — keep it universal, not project-specific | `references/soul-md-is-the-identity-slot-keep-it-universal-not-project-specific-new-2026-06-27-this-user-correction.md` |
| Profile switch vs subagent-as-profile | `references/profile-switch-vs-subagent-as-profile-new-2026-06-27-user-correction.md` |
| Cross-session rule persistence | `references/cross-session-rule-persistence-new-2026-06-27-user-pain.md` |
| What this skill is NOT | `references/what-this-skill-is-not.md` |
| The "should this be a NEW profile?" decision tree | `references/the-should-this-be-a-new-profile-decision-tree-added-2026-06-26-this-user.md` |
| Profile architecture is FLAT — no "main agent" hierarchy (Jun 2026, user explicit) | `references/profile-architecture-is-flat-no-main-agent-hierarchy-jun-2026-user-explicit.md` |
| When dispatch facts come from memory — verify against live state, not recall | `references/when-dispatch-facts-come-from-memory-verify-against-live-state-not-recall-new-2026-06-27-this-user-fresh-session-failure.md` |
| When the user says "have each profile study / research / expand itself" — ask before spawning | `references/when-the-user-says-have-each-profile-study-research-expand-itself-ask-before-spawning-new-2026-06-27-this-user-correction.md` |
| Kanban CLI gotchas | `references/kanban-cli-gotchas-new-2026-06-27-this-session.md` |
| Profile clone trap — `cp -r profiles/X profiles/Y` makes Y a wrong-scope copy | `references/profile-clone-trap-cp-r-profiles-x-profiles-y-makes-y-a-wrong-scope-copy-jun-2026-this-user.md` |
| **When the dispatcher can't tell which of N parallel projects the user is in** (multi-agent setup) — confirm project scope before any `mnemosyne_recall` or `session_search` | **NEW 2026-07-02** → load skill `per-project-context` at `~/.hermes/skills/devops/per-project-context/SKILL.md` (autoloaded via `related_skills: [per-project-context, …]` on the routing path; user feedback 2026-07-02: recall returned cross-project memories instead of the right one) |
| **Personality overlay vs profile spawn vs subagent dispatch** (verified 2026-07-03) — which mechanism for "I want a different voice" and a starter `challenger` personality config | **NEW 2026-07-03** → `references/personalities-vs-profiles-vs-subagents-2026-07-03-this-user.md` |
| **True-forget rule: orphan paths and verified-absent facts** (NEW 2026-07-09, this user) — the user-preference signal that says `mnemosyne_invalidate` with no replacement, NOT a positive "X is absent" memory. Triggered by the 4-session AppData-orphan re-encoding pattern. | **NEW 2026-07-09** → `references/true-forget-rule-2026-07-09-this-user.md` |
| **This skill's version history** | `references/CHANGELOG.md` |

# See also

- `session` — session-open ritual, persistence config, dispatch decisions.
- `security` — credential architecture, pass plugin, threat model.
- `hermes-misbehavior-diagnosis` — agent-side misbehavior patterns.
- `per-project-context` — multi-agent project-scoping discipline for
  `mnemosyne_recall` and `session_search` when the user runs multiple
  parallel agent projects.

## Changelog

Per-skill history: `references/CHANGELOG.md`.
