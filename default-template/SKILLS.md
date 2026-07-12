# hermes-dist SKILLS index (v0.4.8)

> **Read this before `hermes skills install <name>`.** This is the canonical
> index of every skill shipped in `hermes-dist/default-template/skills/`.
> Auto-load skills are loaded into every session's system prompt. Opt-in
> skills are dormant until you explicitly install them.

**Total shipped:** 25 skills (~537 KB across all skill files)
**Auto-load:** 4 skills (~102 KB system-prompt cost per session)
**Opt-in:** 21 skills (install via `hermes skills install <slug>`)

---

## Auto-load (4 skills, ~104 KB system-prompt cost)

These load automatically into every default-profile agent. Do not add
to this list without measuring the impact on first-message latency and
context-window consumption.

### `cartographer-prompt-gate` (v1.2.0, 30.6 KB)

Apply the 5-principles gate before authoring any prompt. Validated by 185-post community sweep on r/PromptEngineering 2026-06-30, then re-validated 2026-07-05 by a templates+architecture sweep that pr

---

### `failures-journal` (v?, 6.4 KB)

When an operation fails or a workflow hits a non-trivial mistake, log it to ~/.hermes/skills/failures-journal/JOURNAL.md (append a dated, structured entry). Check the journal at session start for prio

---

### `mnemosyne-memory` (v2.10.0, 34.1 KB)

Mnemosyne memory subsystem for Hermes Agent — provider wiring, recall discipline, threshold tuning, and dreaming cron. Use when working with mnemosyne store/recall/sleep, debugging memory recall failu

---

### `routing` (v3.1.0, 31.2 KB)

Always-loaded on every query to the default profile. Routes task-specific work to the correct specialised profile (communicate-design, model-merger, prompt-engineering, reviewer, adversary, sandbox, s

---

## Opt-in (install via `hermes skills install <slug>`)

These skills ship in the dist but do NOT load into the system prompt
by default. They become available after explicit user install. They
cover domain-specific disciplines, niche workflows, and tools that
aren't always relevant.

### Category: `background-process-lifecycle/`

- **`background-process-lifecycle`** (v?, 8.3 KB)
  - Launch and track long-running processes from the agent via terminal(background=true) when the user wants the gateway, a watcher, a dev server, or any process that should outlive the terminal call. Cap

### Category: `deep-research-methodology/`

- **`deep-research-methodology`** (v1.1.0, 14.5 KB)
  - 5-layer framework (breadth / depth / time / cross-validation / meta) for expanding research beyond surface-level. Use when the user says 'go deeper' / 'research more' / 'expand' or when initial resear

### Category: `devops/`

- **`hermes-session-open-inventory`** (v1.2.0, 62.9 KB)
  - Use at session start (or before any deploy/upgrade) to verify which tools,
skills, repos, profiles, boards, integrations, AND hermes-state archives
(`~/.hermes-state/{backups,snapshots,patches,temp,st
- **`mnemosyne-curator`** (v1.5.0, 35.4 KB)
  - Use when running the weekly Mnemosyne memory hygiene cron, when memory counts feel bloated, or when the user asks to clean up memories, mark stale memories, or consolidate working memory. Marks stale 

### Category: `hermes/`

- **`hermes-misbehavior-diagnosis`** (v?, 27.7 KB)
  - Use when the agent misbehaves without a clean bug: fabricated results, ignored rules, premature decline, hallucinated state, claims without verification. Triggers on pushback: 'did u even check / view
- **`hermes-skill-loading-disciplines`** (v1.6.0, 65.4 KB)
  - When the framework loads a skill BEFORE the agent tries to use a tool, and the keyword+path+intent triggers that govern which skill fires. Load when (a) the user's request implies persistence to a sec
- **`mnemosyne-tuning`** (v1.1.0, 8.4 KB)
  - Mnemosyne recall-weight and consolidation-tuning recommendations for parallel-session workflows. The current defaults are tuned for general use and can drop high-importance recent content in favor of 
- **`security`** (v2.0.0, 14.4 KB)
  - Security best practices for running Hermes Agent — credential encryption (pass + GPG fallback), approval modes, secret redaction, threat model, and prompt-injection defenses. Load when working on cred
- **`session-continuity-advisor`** (v1.1.0, 13.1 KB)
  - Hermes session lifecycle advisor. Use when (a) the user is starting a new session and asks 'should I start a new session or continue' / 'how should I handle sessions from now on' / 'session discipline

### Category: `meta/`

- **`addon-protocol`** (v1.0.0, 11.9 KB)
  - Threat-tiered sandbox + evidence-loop workflow for any new addon (skill, config edit, cron registration, script, patch). Use when user says 'try something new', 'add X', 'set up Y', 'register Z', or a
- **`cross-session-todo-handoff`** (v1.0.0, 9.4 KB)
  - Cross-session todo continuity for parallel-session workflows. Reads/writes the `work.in_progress` canonical Mnemosyne slot to bridge session boundaries. Use at session START to discover open work from
- **`subagent-resumability`** (v1.0.0, 7.9 KB)
  - Pattern for subagent scratchpad checkpoints + deterministic-UID retry so blocked/killed subagents don't lose work. Use when: (a) spawning a subagent for any non-trivial task, (b) the parent has a chil

### Category: `productivity/`

- **`prompt-interview-pattern`** (v1.0.0, 9.2 KB)
  - Interview the user before writing, one question at a time.

### Category: `prompt-engineering/`

- **`diagnose-root-cause`** (v1.0.0, 5.3 KB)
  - When a fix doesn't work, the cause is usually upstream — not the surface symptom. This is the meta-rule for debugging: patch the cause, not the symptom. Use when you've tried 2+ fixes and the bug pers
- **`prompt-direction-format-examples`** (v1.0.0, 5.6 KB)
  - The 5-step prompt ladder — Direction → Format → Examples → Evaluate → Divide-Labor. Use when a first-pass prompt came back wrong, when delegating to a sub-agent, or when the model picked a tone/format
- **`socratic-prompting`** (v1.0.0, 5.4 KB)
  - 3-questions pattern for strategic work — ask (1) what's the real goal, (2) what constraints am I missing, (3) what's the smallest version I can test — BEFORE doing the task. Use for architecture decis

### Category: `research/`

- **`information-validation`** (v1.2.0, 23.9 KB)
  - Cross-reference methodology: validate claims from multiple independent sources, search for concrete data, question 'best'/'must have' assertions, and apply critical thinking universally. ALSO fires fo
- **`web-interaction`** (v1.0.0, 10.2 KB)
  - Techniques for browser automation, web scraping, and interacting with JS-heavy sites that resist normal tooling.

### Category: `skill-library-consolidator/`

- **`skill-library-consolidator`** (v1.5.0, 41.7 KB)
  - Class-level workflow for surveying the Hermes skill library, detecting contradictions between adjacent skills, and producing a plan to archive, fold, or refactor. Use when the user says 'consolidate',

### Category: `software-development/`

- **`cross-platform-bash-scripting`** (v1.2.0, 39.1 KB)
  - Write bash scripts that run on Windows MSYS/Cygwin, Mac, and Linux without forking — OSTYPE-aware path resolution, extension dispatch, env-var-with-default-fallback, the cmd //c Windows-only trap, the
- **`verify-before-claim-hardware`** (v1.4.0, 15.0 KB)
  - Universal 'verify before claiming' discipline for any state-claim about hardware, services, containers, or files. Use when the user asks about hardware/peripheral/display/network/process state, OR whe

---

## How to use this index

1. **Read the description** for each skill to decide if it's useful for you.
2. **Install with `hermes skills install <slug>`** — the skill gets copied to
   your `~/.hermes/profiles/<uuid>/skills/<slug>/` and becomes available.
3. **Don't install everything.** Each installed skill adds to your context
   load. Install only the skills you'll actually invoke.
4. **If a skill's name doesn't appear in this index**, it's NOT shipped in
   hermes-dist. You can author your own in `~/.hermes/skills/<category>/<slug>/`.

## Source-of-truth for skill authoring

When you want to author or modify a skill, follow the discipline in
`meta/addon-protocol` (opt-in) — the 7-step ADDON procedure for
adding new skills safely. After authoring, log the change via
`~/.hermes/scripts/hermes-changelog.py` so other agents in parallel
sessions see the new skill via the Mnemosyne shared surface.

## Indexes by purpose

- **For research work:** `research/information-validation`,
  `research/web-interaction`, `deep-research-methodology`,
  `prompt-engineering/socratic-prompting`
- **For hermes internals:** `hermes/security`,
  `hermes/mnemosyne-memory`, `hermes/mnemosyne-tuning`,
  `hermes/hermes-misbehavior-diagnosis`, `hermes/hermes-skill-loading-disciplines`,
  `hermes/session-continuity-advisor`, `meta/cross-session-todo-handoff`,
  `meta/subagent-resumability`
- **For shell scripting:** `software-development/cross-platform-bash-scripting`,
  `software-development/verify-before-claim-hardware`
- **For cross-session sync:** `hermes/mnemosyne-tuning`,
  `meta/cross-session-todo-handoff`, `meta/subagent-resumability`
- **For prompt engineering:** `meta/cartographer-prompt-gate`,
  `prompt-engineering/prompt-direction-format-examples`,
  `prompt-engineering/diagnose-root-cause`,
  `prompt-engineering/socratic-prompting`,
  `productivity/prompt-interview-pattern`
- **For long-running services / daemons:**
  `background-process-lifecycle`
- **For fail-loud-on-errors culture:** `failures-journal`,
  `hermes-misbehavior-diagnosis`, `verify-before-claim-hardware`

## Versioning

Skills follow semver. The dist repo's `config.yaml` records the
opt-in catalog; the v0.4.x line ships ~520 KB total opt-in surface
with no auto-load change since v0.4.0. Breaking changes to existing
skills bump the minor version; new skills are added without version
bumps to the catalog.
