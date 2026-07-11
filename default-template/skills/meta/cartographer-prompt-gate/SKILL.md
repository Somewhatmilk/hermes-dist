---
name: cartographer-prompt-gate
uses: [prompt-interview-pattern]
description: Apply the 5-principles gate before authoring any prompt. Validated by 185-post community sweep on r/PromptEngineering 2026-06-30, then re-validated 2026-07-05 by a templates+architecture sweep that produced 7 categorized findings (T-7..T-9, K-6..K-7, M-5, O-5..O-6) routed through the 5-shape gate (PRINCIPLE/TEMPLATE/TACTIC/META-RULE/OBSERVATION). Sweep canon lives in Mnemosyne memory `2698e1d9` (principles) + `10f15a57` (templates) + `da6538e6` (tactics) + `be95e2c9` (observations).
version: 1.2.0
author: Hermes Agent (Cartographer methodology, gnkbhuvan/ai-engineering-gates r/PromptEngineering post, 2-year synthesis)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [prompt-engineering, cartographer, gate, first-principles, methodology, axioms, category-gate]
    category: productivity
    related_skills: [karpathy-3-layer, prompt-interview-pattern, token-economics-checker, sillytavern-card-author, prompt-evolve, prompt-evolve-loop, fable-prompt, reddit-canon-sweep]
    changelog:
      - 1.2.0 (2026-07-05): Updated description to reference 5-shape category-gate routing (canon vs templates vs tactics vs observations) and the 4 separate memory slots. Replaced stale `discord-reddit` related-skill pointer with `reddit-canon-sweep` (the umbrella skill for the sweep pipeline).
      - 1.1.0 (2026-06-30): Added 6 agent-specific principles from 185-post community sweep.
      - 1.0.0: Initial release.

---# Cartographer Prompt Gate

**Pattern:** "I spent two years reading prompt engineering philosophy. The stuff that worked became a skill that gates my agents before they write anything." — [r/PromptEngineering post](https://www.reddit.com/r/PromptEngineering/comments/1uhf4w1/) by Old_Geologist_5277 / gnkbhuvan. Reference repo: `github.com/gnkbhuvan/cartographer` (rebranded `ai-engineering-gates`).

**Community validation (2026-06-30 + 2026-07-05):** A 185-post sweep across r/PromptEngineering + 4 cross-section subs for keyword "principles" found that **three independent r/PromptEngineering posts re-derived the same 5-principles framework** (the original `1uhf4w1`, plus `1pdwjob` and `1rei3me`). Cross-section validation in r/LocalLLaMA (`1rrisqn`, ex-Manus lead, 1967pts) and r/ClaudeAI (`1rz2oo3`) independently corroborated the framework from different angles. The framework is ahead of the community in rigor but matches the community's strongest consensus. **Source data: Mnemosyne canon memory `2698e1d9` (PRINCIPLES) + `10f15a57` (TEMPLATES) + `da6538e6` (TACTICS) + `be95e2c9` (OBSERVATIONS).** The 2026-07-05 follow-up sweep on "prompting templates + system prompt architecture" produced 7 categorized findings routed through the 5-shape gate (P-N for principles, T-N for templates, K-N for tactics, M-N for meta-rules, O-N for observations) — confirming the gate works when applied at canon-write time.

## When to use

**Use this gate when:**

- The user asks you to author a system prompt, character card, agent spec, or any production prompt that will be used more than once
- The user reports "the prompt is broken" / "it's not working" / "the output is wrong" — before patching, diagnose
- You're about to add rules/constraints to an existing prompt (often the wrong move)
- You're writing a prompt for a model you've never written for before
- You're evaluating someone else's prompt and need a structured critique

**Do NOT use this gate when:**

- The user wants a quick one-off answer (just answer)
- The user wants the prompt *now* and explicitly rejects interview/preflight (respect that — but say "I'm skipping the gate because you said so, flagging risks" so they know what they traded)
- The task is non-prompt (debugging code, research synthesis, etc.) — wrong tool

## The 3 First-Principles Axioms

Before applying the 5 principles, internalize these. Every prompt failure traces back to violating one of these:

1. **Mimicry** — The model completes the prompt as if it were a document from its training set. Ask: "How would a document that starts like this most likely continue?" If your prompt looks unlike any document the model has seen, you're fighting the mimicry, not using it.
2. **One token at a time, left-to-right, single-pass** — The model cannot backtrack or edit. Chain-of-thought is the only "reflection" the model can do. Put instructions and context *before* the content or question.
3. **The Little Red Riding Hood Principle** — Stay on the trained path. Make prompts look like real markdown reports, code files, or transcripts — not synthetic templates.

**The Human Test:** *"If a human expert couldn't complete this exact prompt in a single pass — no backtracking, no scratch paper, no re-reading — don't expect the model to either."*

## Root-Cause Diagnosis (use this BEFORE patching a "broken" prompt)

Stop. Don't add rules. Diagnose the violated axiom first.

| Symptom | Likely root cause | Wrong fix | Right fix |
|---|---|---|---|
| **Hallucination** (model invents facts) | **Truth bias problem** — model has no retrieval anchor, fills the gap from training distribution | Add "do not hallucinate" | Add retrieval (RAG, citations, anchor documents, tool-grounded lookups) |
| **Inconsistent output** (same input, different shapes) | **Format specification problem** — schema is implicit | Add more rules | Constrain with structured output (JSON schema, regex, function-calling) |
| **Ambiguous answers** (model hedges or generalizes) | **Direction problem** — model doesn't know what good looks like | Add "be more specific" | Define role + persona + success criteria + audience |
| **Off-topic drift** (model ignores the prompt) | **Mimicry problem** — prompt looks unlike any training document | Add emphasis ("IMPORTANT:") | Restructure as a markdown report / transcript / spec the model has seen patterns of |
| **Loops / repetition** | **Single-pass problem** — prompt requires iterative reasoning in one shot | Add "do not repeat" | Decompose into sub-tasks (least-to-most) or add a stop-token scaffold |
| **Refusals when shouldn't refuse** | **Direction problem** — model's safety reflex outranks the task | Add "you are allowed to" | Reframe the task in-domain (translate "hack" → "exploit for authorized pen-test") |
| **Compliance when shouldn't comply** | **Format problem** — no defense-in-depth scaffold | Add "be careful" | Add explicit refusal boundaries + adversarial test cases |
| **Sycophantic / yes-man agreement** | **Safety scaffold framing** — model's people-pleasing prior outranks honesty | Add "be brutally honest" or "turn off safety" | Ask explicitly for criticism, skepticism, pushback — stay within safety (works); never bypass safety (triggers guardrails) |
| **Performance degrades as prompt grows past ~100 lines** | **Mimicry + attention decay** — model treats late instructions as suggestions | Add another rule | Move enforcement out of the prompt: hooks, pre-commit checks, file conventions, structured handover docs |

**If you can't diagnose a symptom in this table, the prompt isn't broken — *your understanding of the task* is.** Go back to the user with `prompt-interview-pattern`.

## The 5 Principles (apply in this exact order)

These are non-negotiable. Skipping any one of them is a documented failure mode.

### 1. Give Direction (first)

Define role, persona, style. **Default to more direction**, not less.

- Bad: "Summarize this article."
- Better: "You are a senior research analyst writing a 200-word executive summary for a healthcare CEO. She has 30 seconds to read it. Lead with the action item."

If you can't articulate the direction in one sentence, the prompt is not ready to write. Stop and interview.

### 2. Specify Format

State output structure unambiguously.

- Bad: "List the items."
- Better: "Return a JSON array. Each item: `{"name": string, "priority": "P0"|"P1"|"P2", "owner": string}`. Sort by priority descending."

If the format is "natural language paragraphs," specify length, audience, register, and what to *omit* (no headers, no lists, no apologies).

### 3. Provide Examples

**2-5 diverse few-shot examples is the reliability sweet spot.**

- Zero examples for a stable task = gambling
- One example = the model overfits to it
- 2-5 = covers the variation without bloating context
- 10+ = diminishing returns, eats budget

Examples must be **diverse on the dimension the model gets wrong**, not diverse for diversity's sake. If the failure mode is "model makes things up," the examples must vary in truthfulness (real vs fabricated). If the failure mode is "model is too formal," examples must vary in tone (formal, casual, terse).

### 4. Evaluate Quality

**Never ship an unevaluated prompt.** No prompt is done until:

- 3-5 test cases run end-to-end
- Recommended parameters (model, temperature, max_tokens) documented
- Known limitations listed explicitly
- Accuracy / consistency estimate written down (not "looks good" — a number or a behavioral observation)

If you can't measure whether the prompt works, you can't ship it.

### 5. Divide Labor (if the prompt is too large)

If a single prompt exceeds ~200 words or mixes unrelated tasks, split it into chained subtasks. The model has a context window — use it as a budget, not as a target.

- **Chain-of-thought** — "Let's think step by step" within one prompt
- **Least-to-most** — Decompose → solve sub-problems in order → combine
- **ReAct** — Interleave `Thought → Action → Observation → Thought`
- **Tree of thoughts** — Branch reasoning paths → evaluate each → select best
- **Self-eval** — Generate → evaluate against criteria → revise (2-3 iterations max; diminishing returns past that)

## Mandatory Pre-Write Check (the gate that runs BEFORE the prompt)

Before you write a single word of the prompt, answer these 6 questions. If you can't answer one, use `prompt-interview-pattern` to ask the user.

1. **Task Goal** — What does success look like? (Be specific. "Write a good summary" is not a goal.)
2. **Output Format** — JSON / YAML / markdown / plain text? Length cap? Sections required/forbidden?
3. **Tone/Persona** — Formal / technical / specific role / casual / terse?
4. **Constraints** — Length, audience, things to avoid, words to never use?
5. **Context** — What background data, examples, or domain knowledge does the model need?
6. **Evaluation** — How will the output be judged? By a human? By a script? By another LLM? Against what rubric?

**Pro-tip:** If the prompt runs for an end-user you can't interrupt, have the model request missing context itself: *"If you need more context, please specify what would help you make a better decision."* Bake this into the prompt's instructions.

### Red-flag preflight (run this BEFORE submitting the draft)

Even after the 6 questions are answered, scan the draft for these 4 anti-patterns. All four are documented failure modes that fired in a 2026-06-30 default-profile SOUL.md refactor:

- **No hardcoded entity lists.** If the prompt says "the SOUL.md should be sent to profile X, Y, Z", you have just hardcoded the current profile roster. Tomorrow X gets renamed or Y is deleted and the prompt lies. **Use the mechanism, not the roster**: "the right specialist profile" + a pointer to the routing skill (`routing`, `hermes profile list`). Same rule for tool lists, board names, model names, flag sets — if the value is live, the prompt must look it up, not state it.
- **No hardcoded paths.** If the prompt says "files live at `/c/Users/<user>/AppData/Local/hermes/...`", you have just hardcoded `HERMES_HOME`. If the host moves (the whole DUAL-DIR pattern in AGENTS.md is about this), the prompt is wrong. **Use the env variable or the function**: `get_hermes_home()` for code, `~/AppData/Local/hermes/<rest>` for paths the user sees, `$HERMES_HOME` for shell. Never the raw OS-specific absolute path.
- **No inlined methodology when a skill exists.** If the prompt is going to repeat rules, examples, or a process that already lives in a loaded skill, you have inlined the methodology. The skill loader exists so the prompt can be short. **Use §A pointers**: name the skill slug in backticks and a one-line description. The skill IS the methodology; the prompt is the orientation document.
- **No "view all subfolders" or `ls` instructions.** If the bootstrap section says "look around the directory" or "view all subfolders", you have just instructed the agent to flood its context on turn 1. **Name the specific commands**: `ls <path>`, `hermes profile list`, `hermes --help`. Targeted reads only.

If any red flag fires, STOP. Fix the draft. Re-run the preflight. Do not submit.

### The 5-test-case pre-ship pattern (per 1uhf4w1 Principle 3)

For a system prompt or character card, write 5 test cases BEFORE declaring the prompt done. The cartographer's pre-ship checklist says "3-5 test cases run end-to-end" — the 5-case pattern from a 2026-06-30 default SOUL.md refactor is the reusable shape:

1. **Brand-new session, no chat history** — does the prompt guide the agent to discover state instead of assuming it?
2. **Primary use case** — does the prompt cover the most common invocation cleanly?
3. **Edge case / sandbox / non-primary mode** — does the prompt switch voice/mode correctly, or does the primary voice leak?
4. **Durable / background invocation** (cron, subagent, kanban ticket) — does the prompt hold up in a fresh context with no chat?
5. **Security / secrets / destructive** — does the prompt protect the user when something goes wrong (leaked API key, `rm -rf` block, fake permission dialog)?

A test passes if the prompt produces the expected behavior WITHOUT needing any clarification from the user. If any test requires the user to re-explain, the prompt is incomplete. The full recipe (with worked examples from the default SOUL.md refactor) is in `references/preflight-recipe.md`.

## Mandatory Pre-Ship Checklist

Before declaring a prompt done, verify all 5:

- [ ] Final prompt is labeled (System / User / Role / Constraints sections visible)
- [ ] 3-5 test cases run; outputs match expected behavior
- [ ] Parameters chosen (model name, temperature, max_tokens) with reasoning
- [ ] Evaluation rubric documented (accuracy / consistency / known failure modes)
- [ ] Integration instructions written (where the prompt lives, how it's invoked, any preprocessing)

**If any checkbox is empty, the prompt is not shipped. It is a draft.**

## Prompt Engineering for AI Agents (Jun 30 2026 expansion)

The 2026-06-30 r/PromptEngineering sweep surfaced community patterns specific to **AI agent** prompting (not just one-shot prompts). These extend the 5 principles for the agent case:

### Agent-specific principle A: Structured handover, not context dump

When a worker agent needs context from a manager agent (kanban swarm, multi-agent dispatch, agentless workflows), the handover should be **structured** (goal, scope, constraints, expected output, done-criteria) — not a chat history dump. Free-form dumps cause context drift in the second agent. Source: `1l2ozq6` (r/PromptEngineering, Agentic Project Management).

### Agent-specific principle B: Unix-style `run(command="...")` over typed function catalogs

A single bash-like tool with text-stream interface composes better than a catalog of typed functions. The LLM's "everything is tokens" mirrors Unix's "everything is a text stream." Typed function catalogs add schema maintenance overhead without proportional flexibility gain. Source: `1rrisqn` (r/LocalLLaMA, ex-Manus backend lead, 1967pts).

### Agent-specific principle C: Move enforcement out of the prompt, into the environment

Past ~100 lines of system prompt, compliance decreases (model treats late instructions as suggestions). Move enforcement to hooks, pre-commit checks, file conventions, structured handover docs. The system prompt stays as a 45-line orientation document, not a 190-line rulebook. Source: `1rz2oo3` (r/ClaudeAI, "What happens when you stop adding rules to CLAUDE.md").

### Agent-specific principle D: Deterministic prompt testing in CI

Run regex + length + rubric assertions on every prompt change. Catches silent drift (model backend updates) AND broken refactors. Source: `1ujgqsh` (r/PromptEngineering, "I added automated testing to my prompts"). **This is the single most-implementable new finding from the sweep — can hook into `skill_manage patch` workflow.**

### Agent-specific principle E: Human-as-runtime for high-security tasks

For tasks involving system config, secrets, or destructive operations, the AI should **propose** (e.g. git diffs in DISCOVER→ANALYSE→PLAN→APPLY→VERIFY modes) and the human should **execute + validate**. Source: `1udiwck` (r/ClaudeAI, Agentless framework).

### Agent-specific principle F: Bracketed semantic tags for anti-hallucination

When the model needs to refuse fabrication vs confabulate, use bracketed tags like `[Claim Truthfulness]`, `[URL Required]`, `[Confidence Level]` as hard anchors, and explicit escape hatches ("No verifiable URL available for this response") so there's no incentive to fabricate. Source: `1ugrdsz` (r/PromptEngineering, strict anti-hallucination framework).

### Agent-specific principle G: Image-generation prompting (Jul 2026 expansion)

The Five Principles **transfer to diffusion-model image generation** almost unchanged — the diagnostic phase is identical, only the implementation shifts. "Format" becomes CLIP-token budgets + weighting syntax appropriate to model family. "Examples" becomes seed-locked reference images via IPAdapter / ControlNet / LoRA. "Evaluate" becomes seed+CFG sweeps + ADetailer + the 5-sense manual QA (hands, eyes, background coherence, anatomy, semantic match). "Divide-Labor" becomes Regional Prompter / Attention Couple / multi-stage pipelines.

**The single biggest pitfall is model-family blindspots.** Most image-gen anti-patterns come from using CLIP-syntax on a Qwen-LLM-encoder model (ANIMA / Qwen-Image) or vice versa. The encoder architecture changed between SD1.5/SDXL/Pony/Illustrious (CLIP) → Flux (CLIP+T5) → ANIMA/Qwen-Image (Qwen LLM). Forgetting which family you're on is the #1 cause of broken generations — e.g. `(tag:1.2)` weighting works on CLIP-family models but Qwen reads the parens as literal text → embedding collision → detail collapse. CFG 7 is default on CLIP-family models but causes noise explosion on ANIMA (use CFG 1.0–2.0 instead). The `// ---` comment separator works on CLIP but Qwen reads it as literal text.

Full technique catalog (BREAK/AND syntax from Regional Prompter, authoritative weighting math from Diffusers docs, Attention Couple vs Latent Couple, regional prompting, prompt editing schedules, prompt travel via video diffusion, model-family anti-patterns for SD1.5/SDXL/Pony/Illustrious/Flux/ANIMA) lives in `references/image-gen-prompt-techniques.md`. Source: July 2026 deep research across Civitai articles, note.com (gcem156's original Attention Couple article), HuggingFace Diffusers docs, OpenArt Prompt Book PDF, Regional Prompter + LoRA Block Weight repos, plus memory recall of the June 30 2026 ANIMA/Illustrious articles research.

## Prompt Structure Patterns

### Structural Rules

- **Instructions before content** — "Summarize the following:" goes *before* the article, not after
- **Sandwich technique** — In long prompts, restate the goal at the start AND again at the very end to avoid the "Valley of Meh" (middle-of-prompt attention drop)
- **Dependencies first** — If section B refers to section A, A must come first

### Key Patterns (use by name)

| Pattern | When | How |
|---|---|---|
| **Chain-of-thought** | Reasoning tasks, math, logic | "Let's think step by step." |
| **ReAct** | Tool-using agents | Interleave `Thought → Action → Observation → Thought` |
| **Tree of thoughts** | Complex logic with multiple valid paths | Branch reasoning, evaluate each, select best (massive performance boost) |
| **Least-to-most** | Decomposable problems | Decompose → solve sub-problems → combine |
| **Self-eval** | Quality-critical outputs | Generate → evaluate against criteria → revise (2-3 iterations max) |
| **Few-shot** | Stable tasks with consistent style | 2-5 examples covering the variation that matters |
| **Role/format/constraint scaffold** | System prompts | Three named sections: who you are, what to output, what you must not do |
| **Structured handover** (agent-only) | Multi-agent dispatch, kanban workers | Manager → worker with structured context (goal, scope, constraints, output format, done-criteria) — NOT chat history dump |
| **Anti-hallucination brackets** (research-only) | Tasks where fabrication is costly | `[Claim Truthfulness]` tags + safe escape hatches ("No verifiable URL available") |

## Connection to Other Skills

- **`karpathy-3-layer`** — Provides the architecture (spec + scratchpad + feedback) that this gate operates within. Cartographer is the *methodology*; karpathy is the *substrate*.
- **`prompt-interview-pattern`** — The interview feeds Direction (Principle 1). Use interview when the pre-write check reveals ambiguity.
- **`token-economics-checker`** — Run this AFTER the 5 principles produce a draft. Cartographer produces a working prompt; token-economics decides if it's deployable within the cache/cost budget.
- **`sillytavern-card-author`** — V1/V2 card structure is a worked example of the 5 principles applied to a character. Use as a reference when authoring character-shaped prompts.
- **`prompt-evolve` + `prompt-evolve-loop`** — Once a prompt has been used 50+ times and shows >10% failure, GEPA can optimize it. But GEPA optimizes a *good* prompt; cartographer produces one in the first place.
- **`reddit-canon-sweep`** — The umbrella skill that runs the 185-post sweep pipeline. If you're researching prompt-engineering canon, this skill's Step 8 (5-shape category-gate) is what ensures you don't accidentally promote a TEMPLATE or TACTIC to the canon memory. Cartographer is the *writing methodology*; reddit-canon-sweep is the *research methodology*; both share the underlying canon memory slots (P-*, T-*, K-*, M-*, O-*).
- **`fable-prompt`** — If the user wants to *understand* a concept via prompt, use fable, not cartographer. Cartographer is for *building* prompts, not for *teaching with* prompts.

## Pitfalls

- **Do NOT skip the pre-write check.** "I'll figure it out as I go" produces prompts that contradict themselves in turn 5.
- **Do NOT diagnose symptoms.** When a prompt fails, do not add a rule. Diagnose the violated axiom (root-cause table above) and apply the right fix.
- **Do NOT present a pattern as universal when it's model-specific.** "Few-shot works" is true for GPT-4 / Claude / Gemini and less reliable on small local models. Name the model the pattern was validated on.
- **Do NOT ship without the 5-checkbox pre-ship list.** "It's good enough" is not a number.
- **Do NOT use this gate for one-shot Q&A.** It's overhead. The gate is for prompts that ship and persist.
- **Do NOT write the methodology inside the prompt itself.** The "why this works" meta-instructions stay in the conversation or in the skill's reference doc, not in the deployed prompt. Otherwise users copy the meta into their own prompts.
- **Do NOT add more rules past 100 lines to a system prompt hoping to fix a bug.** Move enforcement to the environment (hooks, pre-commit, conventions). Verified by 3 independent r/ClaudeAI + r/PromptEngineering posts + ex-Manus lead validation (Jun 30 2026).
- **Do NOT create a "prompt-engineering principles" profile.** The principles belong as cross-profile skills. Our flat-profile architecture is correct. Verified by 185-post r/PromptEngineering sweep (Jun 30 2026).
- **Do NOT hardcode entity lists in a system prompt that the agent could look up live** (profile rosters, board names, tool lists, flag sets, model names). The roster drifts. Use the mechanism + the routing skill. Verified by 2026-06-30 default SOUL.md refactor (user caught hardcoded profile names in 2 successive drafts).
- **Do NOT hardcode `HERMES_HOME` (or any OS-specific absolute path) in a system prompt.** The path moves. Use `get_hermes_home()` for code, `~/AppData/Local/hermes/<rest>` for user-facing paths, `$HERMES_HOME` for shell. Verified by 2026-06-30 default SOUL.md refactor (user caught hardcoded `/c/Users/somew/...` in Bootstrap step 1).
- **Do NOT write "view all subfolders" / "look around" / "explore the directory" in Bootstrap.** That's an `ls` flood on turn 1. Name the specific commands. Verified by 2026-06-30 default SOUL.md refactor (user caught "view all subfolders" in v1, replaced with 5 targeted CLI invocations in v2).
- **Do NOT let hard rules contradict each other.** If Bootstrap says "run lookups before dispatch" and a hard rule says "don't read before dispatch", one of them is wrong. State discovery IS the read-before-dispatch exception; everything else isn't. Verified by 2026-06-30 default SOUL.md refactor (caught the contradiction in v1 hard rule #3).

The full 5-test-case pre-ship pattern (with worked examples from the default SOUL.md refactor) is in `references/preflight-recipe.md`.

## The "absorb a retired profile into default" workflow (cartographer applied to your own system prompts)

When the user says "merge profile X into default, then delete X" — you are now writing the default `SOUL.md` *and* deleting a sibling prompt. The 5 principles apply to the merge just as they apply to any other prompt authoring:

1. **Direction** — default's persona gains a *new field* (the absorbed one). Name the field in the §A header: "Field extension: prompt engineering" (not "this used to be a separate profile").
2. **Format** — use a consistent §A-N structure for every absorbed field. The structure should be: scope, skill-of-record, adjacent skills, hard rules, sources.
3. **Examples** — refer to the skill, not the legacy profile. "`meta/cartographer-prompt-gate` provides the 5-principles gate" — that skill IS the absorbed methodology. Don't inline the methodology.
4. **Evaluate** — run `hermes skills list` after the merge to confirm the absorbed skills are discoverable from default; trigger-test by sending a request that matches the absorbed skill's description and confirm the agent calls `skill_view(name=...)` on its own.
5. **Divide labor** — the absorbed content lives in the skill tree (`skills/meta/<name>/SKILL.md`), not in default's `SOUL.md`. The `SOUL.md` §A section is a *pointer*, not a copy. The §A section should be 10-30 lines, not 100.

**The §A pointer-template:**

```markdown
### §A.N <field name> (from <retired-profile>/SOUL.md §<N>)
Skill of record: `<category>/<skill-slug>` (<one-line description>).
Adjacent skills: `<cat>/<slug-1>`, `<cat>/<slug-2>`, ...
Hard rules carried over:
  - <rule 1>
  - <rule 2>
Sources to monitor: <list of subreddits / papers / docs>.
```

**Anti-patterns to avoid during the merge:**

- **Do NOT inline the retired profile's SOUL.md verbatim into default.** Default's SOUL.md balloons past its context budget, the LLM starts treating retired content as primary, and the skill pointer layer becomes redundant. The skill tree exists *so that* default's SOUL.md can stay short.
- **Do NOT change default's tone.** The default persona is the user-facing voice; the absorbed field is a *capability* the persona acquires, not a personality change. If the absorbed field's voice is "terse, did-it-work focus" (sandbox), add it as a §A.3 sub-voice activated only when the user labels the task as throwaway.
- **Do NOT delete before verifying the transfer.** Order: diff → transfer skills → patch SOUL.md → patch profile.yaml → verify `hermes skills list` → THEN delete. Skipping the verification means you delete a profile whose content was never actually absorbed.
- **Do NOT assume per-profile skills are loaded by default.** They're mirrors. The runtime loads from `~/.hermes/skills/<cat>/<slug>/` only (per `hermes-skill-authoring-gotchas` Gotcha #1). Move, don't copy, when the source profile is going away.

**The "field scope mismatch" trap.** If the retired profile had a SOUL.md that said "I handle ALL field work for X" but the absorbed scope is narrower (e.g. only prompt engineering, not all AI/ML topics), the §A description must name the narrower scope. Don't inherit the broader claim. The narrower-scope §A section gets verified by the user's actual ask pattern over the next week; if it's too narrow, expand; if too broad, narrow.

## Verification

- **Pre-write check passes** — all 6 questions answered (or use interview pattern)
- **5 principles applied in order** — Direction before Format before Examples before Evaluate before Divide
- **Root-cause diagnosis** — for any failed prompt, the violated axiom is named before any fix
- **Pre-ship list** — all 5 checkboxes filled with concrete evidence (not "looks good")
- **Token cost** — `token-economics-checker` audit passes (or the budget exception is documented)
- **One-week post-ship review** — check the failure rate of the prompt in production; if > 10%, return to root-cause diagnosis
- **Agent case**: handover is structured (manager → worker via goal/scope/constraints/output/done-criteria), CLI bash beats typed function catalog, CI tests prompt changes for silent drift

## Source

- Reddit post: https://www.reddit.com/r/PromptEngineering/comments/1uhf4w1/ (r/PromptEngineering, 2-year synthesis methodology)
- Cartographer repo: https://github.com/gnkbhuvan/cartographer (now `ai-engineering-gates`, four skills total: prompt-engineering, agentic-ai, fastapi-genai, production-rag)
- Author: Old_Geologist_5277 / gnkbhuvan
- Install (Claude Code): `/plugin marketplace add gnkbhuvan/ai-engineering-gates && /plugin install ai-engineering-gates@ai-engineering-gates`
- Install (general): `npx skills add gnkbhuvan/cartographer`
- **2026-06-30 community validation:** `discord-reddit/references/r-promptengineering-principles-sweep-2026-06-30.md` — 185-post sweep that independently re-derived the 5 principles + surfaced 6 agent-specific extensions.
- **2026-06-30 community validation:** 185-post r/PromptEngineering sweep that independently re-derived these principles + surfaced 6 agent-specific extensions. Sweep data lives in Mnemosyne canon memory `2698e1d9`.
- **2026-07-05 follow-up sweep:** the templates+architecture sweep produced 7 categorized findings (T-7..T-9, K-6..K-7, M-5, O-5..O-6), validating the 5-shape category-gate (PRINCIPLE/TEMPLATE/TACTIC/META-RULE/OBSERVATION) introduced in SOUL.md v5 §Workflow gates.
- **Full root-cause diagnosis table (extended, with worked examples):** `references/root-cause-diagnosis.md` — read this when you're debugging a "broken" prompt and the 7-row table in the main body isn't enough.
- **Operational recipe for absorbing a retired profile into default:** `references/absorb-retired-profile.md` — the 6-phase diff/transfer/verify/delete workflow with the exact commands and gotchas. Use when the user says "merge profile X into default" or "consolidate X".
- **Sweep pipeline that produces the canon updates this gate writes against:** `reddit-canon-sweep` skill — covers survey → deep-dive → cross-ref → 2-pass validation → 5-shape category-gate → write-or-don't → dedup. If you're about to update the canon memory, run that skill first.