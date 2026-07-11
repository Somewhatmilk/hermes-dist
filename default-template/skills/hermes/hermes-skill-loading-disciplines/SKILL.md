---
name: hermes-skill-loading-disciplines
uses: [hermes-session-open-inventory]
description: "When the framework loads a skill BEFORE the agent tries to use a tool, and the keyword+path+intent triggers that govern which skill fires. Load when (a) the user's request implies persistence to a second-brain tool (Obsidian, Notion, logseq, vault, 'remember this'), (b) the user names a path that resolves to a SKILL.md, (c) any `write_file` is being planned and a matching skill exists for the destination tool, or (d) you are debugging why an agent substituted CWD writes / shell scripts for the proper tool."
version: 1.6.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, skills, tool-routing, obsidian, notion, dispatch, vocabulary, second-brain]
    related_skills: [obsidian, notion, hermes-profile-taxonomy, hermes-agent]

---# Hermes Skill-Loading Disciplines

When to use this skill: deciding WHETHER to load a skill before performing an action. Covers the three load triggers (path-named, keyword-implied, tool-implied) and the failure mode when they're missed.

## Background

Hermes agents have a 100+ skill library under `~/.hermes/skills/`. Skills are bundles of:
- A `SKILL.md` with YAML frontmatter (description, tags, trigger conditions)
- Optional `references/`, `templates/`, `scripts/` directories
- Procedural knowledge for a class of task

Skills are LOADED via `skill_view(name)` and become injected context. Without loading, the agent does not know the skill's procedures, gotchas, or which tool is its primary surface.

The problem: **an agent will fall back to whatever works in plain text** (write_file to a CWD .md, terminal scripts, raw curl) when it does not realize a dedicated skill exists. This is silent — the user sees a .md appear, doesn't realize it landed in the wrong place.

## Three trigger classes

### 1. Path-named trigger (already in default SOUL.md rule #5)

> *"When the user's request names a path under `~/.hermes/skills/` that exists and contains a `SKILL.md`, treat that as an explicit skill invocation for this turn: load that `SKILL.md`, follow its workflow, and return only its outputs."*

**Caveat:** only fires when the path is explicit. The user has to write something like "use the obsidian skill" or "look at ~/.hermes/skills/devops/foo/SKILL.md". Bare mentions of "obsidian" without a path miss this.

### 2. Keyword-implied trigger (NOT YET in default SOUL.md — proposed as rule #6)

**Trigger words / phrases that imply a dedicated skill should be loaded:**

| Domain | Trigger words |
|---|---|
| Vault / second-brain | `obsidian`, `vault`, `notion`, `logseq`, `second brain`, `roam`, `notes app` |
| Persistence vocabulary | `remember this`, `save for later`, `note for me`, `write this down`, `keep a record` |
| PARA folder names | `inbox`, `ideas`, `areas`, `initiatives`, `resources`, `archive`, `projects` |
| File artifacts | `journal`, `log entry`, `session journal`, `retrospective`, `entry log` |
| Versioning / sync | `commit this`, `sync to`, `push to`, `save snapshot` |

**Discipline:** before any `write_file` whose destination is uncertain, scan the user's request for these trigger words. If matched, `skill_view(name)` for the matching skill first. If the trigger word maps to a tool (Obsidian, Notion) but the skill does not exist or has not been loaded, **STOP and load the skill before any write**.

**Rule #6 candidate text** (for default SOUL.md):

> *"When the user's task implies persisting to a vault, journal, or second-brain (Obsidian, Notion, logseq, 'in my notes', 'save for later', 'remember this'), load the matching skill from `~/.hermes/skills/` BEFORE the first `write_file`. Trigger words: `obsidian`, `notion`, `vault`, `journal`, `remember`, `save`, `note`, `logseq`, `second brain`, `knowledge base`. Do not substitute CWD writes."*

### 3. Tool-implied trigger

Triggered by the tool the agent is about to invoke, not by user vocabulary. Examples:

| Tool being invoked | Implied skill |
|---|---|
| `mcp__obsidian__*` (any mcp__obsidian tool) | `obsidian` |
| `delegate_task(profile="reviewer")` | `hermes-profile-taxonomy` (for the rebuttal/dispatch shapes) |
| `cronjob(action="create")` for kanban-style schedules | `kanban-orchestrator` or `cronjob` skill |
| `image_generate(prompt=...)` with a creative intent | a `creative` category skill if one matches the style |
| Any `terminal(command)` that does a Django migration | `software-development/spike` or similar |

**Discipline:** before invoking a tool whose output goes somewhere with a managed surface, check whether a skill owns that surface. If yes, load it. This catches the case where the user says "do X" and X maps to a tool whose semantics require procedural memory.

### 4. Task-shape trigger (NEW 2026-07-04 — added after the dirty-talk.jpg skip)

Triggered by the **shape of the task itself**, not by user vocabulary and not by the tool being invoked. The signal: "this looks like work a known skill governs, even though the user didn't say the trigger word and the tool choice is generic."

**Why this is its own class:** Classes 1–3 all assume SOME signal points to the skill — a path, a keyword, or a specific tool. Task-shape trigger fires when NONE of those are present, but the operation pattern still matches a known skill. The failure mode is treating the missing signal as "no skill matches" and improvising a generic approach.

**Discipline:** when the operation pattern matches a class of work a loaded skill inventory lists, `skill_view(name)` first — even if the user didn't say a trigger word and the tool choice is the generic default (e.g. `vision_analyze` for "image → something", `read_file` for "open this document", `terminal` for "do shell stuff").

**Examples of task-shape matches that should fire a load:**

| Task shape (input → output) | Skill to load |
|---|---|
| Image file on disk → SD prompt / tag string / ComfyUI workflow JSON | `image-style-pipeline` (vision + tagger dual-source workflow, schema check, vocabulary probe) |
| Image file on disk → description for a blog post / caption | still `image-style-pipeline` if any structured output is expected; otherwise general vision_analyze is fine |
| Markdown file → code review | `requesting-code-review` (not just `read_file`) |
| Git diff → merge plan | `hermes-profile-taxonomy` reviewer profile, or `sd-model-merging` if SD-specific |
| Pasted prompt text → "is this a good Illustrious/Animagine/Pony prompt?" | `civitai-research` for model-family conventions + `image-style-pipeline` for the schema check |
| "Give me the WD tagger output for this image" | `image-style-pipeline` — has the `scripts/wd_tagger_local.py` wrapper and preprocessing recipe |

**Anti-pattern (the failure case this class was extracted from):** user pastes `"C:\Users\somew\Downloads\dirty talk.jpg" prompt` — no "analyze", no "describe", no "illustrious" word — and the agent calls `vision_analyze` solo with a generic JSON prompt. The keyword-implied trigger (class 2) doesn't fire because there's no trigger word. The tool-implied trigger (class 3) doesn't fire because `vision_analyze` is generic. But the task shape (image → SD prompt) matches `image-style-pipeline` exactly. Skipping the load → caption-prose output that misses the tag-string schema entirely.

**Rule #7 candidate text** (for default SOUL.md, complementary to rule #6):

> *"When the operation pattern matches a class of work a skill in `~/.hermes/skills/` covers (image → SD prompt, markdown → review, diff → merge plan, etc.), load the matching skill BEFORE improvising — even if the user did not name the skill, did not say a trigger word, and the tool you would have called is the generic default. The trigger is the task shape, not the vocabulary. Missing trigger words is not license to skip the skill."*

### 5. Agent self-tic trigger (NEW 2026-07-05 — from user insight)

Triggered by **the agent's own draft text**, not by user vocabulary, not by tool choice, not by task shape. The signal: phrase tics that the agent reliably says at predictable action moments. When the agent catches itself saying one of these phrases during drafting, the matching skill should be loaded before the response is sent.

**Why this is its own class:** Classes 1-4 are all triggered by user signal or operation pattern — they capture what the task LOOKS like. Class 5 captures what the agent IS DOING. Some actions (pre-flighting a dispatch, recognizing a discovery, acknowledging a failure) have no user-facing trigger word but have a reliable agent-internal verbal tic that fires at the moment of action.

**Examples of agent self-tics that should fire a load:**

| Agent tic (sentence starter or phrase) | Moment it signals | Skill to load |
|---|---|---|
| "Holy shit" / "Massive findings" / "Big find" / "Major red flag" | About to research deeply; structural implication | `subagent-decision-matrix` |
| "Let me pre-flight..." / "First dispatcher profile..." / "Before I delegate..." | About to dispatch a subagent | `session` + `hermes-profile-dispatch-rules` |
| "Mystery solved" / "Root cause was..." / "Now I see it" | Just found a real bug after confusion | `hermes-misbehavior-diagnosis` (write up cleanly for user) |
| "Direct answer first" / "Honest answer to your question" / "Reconstruct" | Under pressure to be candid | `prompt-interview-pattern` (continue the direct style) |
| "I should have caught this" / "You're right" / "Mystery solved" | User caught a failure | `failures-journal` (log + commit to memory) |
| "Let me try a different approach" | Pivoting after 2+ failed attempts | `systematic-debugging` |
| "Loading X skill..." / "Let me skill_view..." | Already loading — cross-check we're loading the right one | (audit-pass only) |

**Anti-pattern (the failure case this class was extracted from):** user asks *"can't u think of an intuitive way to trigger dynamically based on the task and project complexity"* — and the agent responds with a trivia dump about skill loading. The agent DID say "holy shit" several turns earlier upon finding Hermes issue #44637 and the AtlasOmnia two-stage router pattern. That tic signals "important discovery → load the skill I'm about to describe IN MY REPLY → demonstrate it." Skipping the load → agent writes about the pattern instead of using the pattern. User sees a recipe they already implied they wanted applied.

**The mechanism limitation (honest disclosure):** Hermes' loader does substring match against description text at session-start index-build time. It cannot inspect the agent's in-flight draft text. **Class 5 is the agent manually triggering itself**, not a runtime hook. Implementation pattern: keep the tic → skill mapping in `references/agent-self-tics.md`; when the agent catches itself saying one of these phrases during drafting, `skill_view(name)` is called BEFORE the response goes out. This is a self-discipline, not a system feature.

**Rule #8 candidate text** (for default SOUL.md):

> *"When the agent catches itself about to write a phrase from the agent-self-tics table (e.g. 'holy shit' for an important discovery, 'mystery solved' for a real bug found, 'I should have caught this' for an acknowledged failure, 'let me pre-flight' for an imminent dispatch), treat that as a skill-load signal — call `skill_view(name)` for the matching skill before the response leaves the agent. The agent's verbal tics are reliable indicators of the action it's about to take. Ignoring them is silently substituting a generic response for the proper procedural one."*

**Tics to mine for your own usage:** The above table is seed data; each session should add tics it discovers (claim → skill row in `references/agent-self-tics.md`). The discipline compounds — every session that uses the table sharpens the next session's self-recognition.

### 6. Audit-vs-research distinction (NEW 2026-07-05, this user)

Triggered when the **task shape** is "characterize/inventory/verify something the user already has on disk" vs "find out about something external." These look identical from a tool-usage perspective (both involve reading files), but they require different skill combinations:

- **Audit task** (filesystem walk): `hermes-misbehavior-diagnosis` (if something looks broken) + relevant domain skill if one applies. NOT `deep-research-methodology` — that's for external research.
- **Research task** (external sources): `deep-research-methodology` (mandatory — its 5-layer framework catches the single-source failure mode) + `hermes-misbehavior-diagnosis` if results contradict prior knowledge. NOT local filesystem reads of installed packages.

**The failure mode** (verbatim, 2026-07-05): *"why are u viewing my desktop i meant do actual research online with camfox and documentation"*. The agent had been reading 20+ files from `~/.hermes/hermes-agent-self-evolution/` and `Notes/Crody Theory.md` and calling it research. It was an audit. The user wanted external research (live web, GitHub issues, recent discussions).

**The triage table:**

| User says | Class | Skills to load |
|---|---|---|
| "show me what's in X", "audit my install", "what's installed", "categorize Y", "list X", "what do we have" | **Audit** | domain skill (if specific) + your own judgment; NOT `deep-research-methodology` |
| "research X", "find docs on X", "look up Y", "what's the latest on X", "compare X vs Y online", "how does Z actually work in production" | **Research** | `deep-research-methodology` (mandatory — its 5-layer framework catches single-source results) + domain skill if specific |
| "is X correct", "does Y actually work", "verify Z", "audit then research" | **Mixed** | `hermes-misbehavior-diagnosis` first (audit claims), then optionally `deep-research-methodology` (verify externally) |
| "implement X based on my Y", "build me Z", "use what we have" | **Inline build** | relevant implementation skill (`obsidian`, `comfyui-workflow-api`, etc.) — NO external research needed |

**Disambiguation rule:** if the user did NOT name an external source AND did NOT ask to look anything up online, they want an audit. Don't volunteer to web-research something they didn't ask for. If the user said "research" or named an external source explicitly, they want external. The middle case ("audit my notes on X" — implies looking at notes, not the web) defaults to audit.

**The "audit then research" hybrid is real and common.** E.g. user pastes broken CSS and says "why isn't this working" → audit the CSS file first (3-5 reads), THEN if the audit doesn't reveal the bug, escalate to research (did anything change in the loader upstream?). The pattern: audit first (cheap), escalate to research only when audit is insufficient. NOT the reverse.

**Tic phrases that should fire this class:**
- "show me what's installed", "audit", "categorize", "list what we have" → audit
- "research", "look up", "find docs", "latest on" → research
- "this doesn't work, why" → audit first, research if audit fails
- "implement", "build", "use X" → inline build

The kicker: **the user's correction signal itself is the trigger.** When the user types "actually no, that's not research, do it properly", the agent should immediately load `deep-research-methodology` and restart from scratch — not patch the audit-only report with one or two web searches. The audit was a wrong starting point; the whole attempt needs to be redone with the correct skill loaded.

## The failure mode (Pattern 8)

The user explicitly called this out in the 2026-07-04 v4-vs-v5 session:

> *"it doesnt know obisidian is its tool but it had a task related to using obsiidan it then proceed to write on its own markdown and not onto obsidian"*

Translation: the agent was asked to do work involving Obsidian. It wrote markdown files to CWD. Not because CWD was the right place, but because the agent never realized Obsidian was a tool with its own skill.

This is **silent substitution**: the agent degrades gracefully to a worse path because the right path required a skill load. The user has to read the result, realize "this isn't in my vault", and correct it — wasted turns.

## Pattern 9 — silent skill-skip (NEW 2026-07-04)

Pattern 8 covers "wrong destination" (CWD instead of vault). Pattern 9 is the related but distinct failure: **the right tool got called, but the skill that governs *how to use that tool well* got skipped.** The output lands in the right place but at the wrong quality level.

**Translation:** user pastes an image and asks for a prompt. The agent calls `vision_analyze` — the right tool. But the agent does NOT call `skill_view("image-style-pipeline")` first, so it does not know the dual-source merge (vision + tagger), the schema expectation (tag-string, not prose caption), the vocabulary probe (drop invented aesthetic terms), or the pre-post verification gate (compare to existing `_render/prompt-map.json` entries). Output is a prose caption paragraph with invented aesthetic terms — the right destination, the wrong artifact.

**Why this is distinct from Pattern 8:** Pattern 8 is the failure to load the tool skill (write_file vs obsidian tool). Pattern 9 is the failure to load the workflow skill (right tool, generic workflow). Both waste turns; both are silent. The fix for both is the same shape — load the matching skill before improvising — but Pattern 9 requires the task-shape trigger (class 4) because the tool choice is already correct, so class 3 doesn't fire.

**Three tells that Pattern 9 has fired:**

1. The output format doesn't match the format recall surfaces from past-session reference entries in the same domain.
2. The user has to push back on quality ("why was yours different") rather than on destination.
3. A skill that explicitly governs the workflow exists in inventory and was not loaded.

If any two of those three are true after a turn, the audit checklist (below) should fire.

## Pattern 9b — search-canon-skipped (NEW 2026-07-11, this user)

Distinct from Pattern 9. Pattern 9 is "right tool called, workflow skill skipped." Pattern 9b is **"right tool class called, wrong instance within the class — and the rule governing which instance to pick was retrievable but never retrieved before the call."** The output lands in the right class but at the wrong depth/coverage.

**Canonical instance (this session, 2026-07-11):** the user asked *"is your evidence back by anything or do u need to do research like i said"* after the agent made claims about Airbnb photo specs and upscaler choice. The Mnemosyne canon (importance 0.85–0.9, multiple entries) says: research discipline is `tinysearch_research` (primary discovery) → `tinysearch_scrape_url` (deep page read) → `web_extract` (text extraction) → `web_search` ONLY as fallback, with multi-source sweep across Reddit + Gemini + Japanese/Chinese sources for niche topics. **The agent called `web_search` first** — the canon's fallback tier — and got 5 single-source results that were insufficient, then over-corrected with handwaving assertions like "wrong model class" without citing the comparison page (`phhofm.github.io/upscale`) or the canonical 5-stage workflow (Medium "Rescuing lost art with ComfyUI") that `tinysearch_research` surfaced as a top hit on the FBCNN query.

**Why this is distinct from Pattern 9 (silent skill-skip):** Pattern 9 is "workflow skill skipped entirely." Pattern 9b is "workflow skill loaded (or partially followed) but the **tool-instance ordering** inside the workflow was skipped." The search-research canon lives at importance 0.85 in Mnemosyne but is **not** wrapped in a `web-search-discipline` skill — it's a multi-step ritual inside the `research` category's discipline, and there is no skill whose `skill_view` triggers it. So loading the right skill is not sufficient; the agent must also recall the instance-ordering rule before invoking the first search tool.

**Three tells that Pattern 9b has fired:**

1. The user's request implies evidence-citation, source-naming, or "look this up properly" — vocabulary like *"is this evidence-backed"*, *"are you sure"*, *"back it up"*, *"actual research"*, *"don't make it up"*, *"from sources"*. All of these signal: multi-source canon, not single-tool invocation.
2. The agent called `web_search` as the **first** search-class action without recalling the search-research canon. `tinysearch_research` was the canonical first call (it does a multi-engine crawl + ranked page return, surfacing non-obvious sources like Medium workflows, GitHub READMEs, model cards, and forum threads that `web_search`'s 5-result cap misses).
3. The agent's claim cites a single URL or single engine ("I read X") when the canon requires multi-source triangulation across at least 2 engines + at least 1 community/forum source for niche-class topics.

**The discipline when any of these tells fires:**

1. STOP before the first `web_search` / `terminal(curl)` / browser nav. Run `mnemosyne_recall(query="search research canon tinysearch web_search order", limit=3)`. The top hit will name the canonical ordering.
2. If the canon exists and names a primary tool, **call that tool first**, not `web_search`. `tinysearch_research(query)` returns 5–10 ranked URLs spanning multiple engines; that's the discovery surface; `web_search` is the fallback.
3. If the canon is missing from recall (fresh install, fresh memory), default to `tinysearch_research` → `tinysearch_scrape_url` → `web_extract` → `web_search` — the canonical instance-ordering lives in Mnemosyne, not in any single skill.
4. After 1+ `tinysearch_research` call, scrape the top 2–3 URLs with `tinysearch_scrape_url` or `web_extract` to get the dense page content. `web_search` results give previews; `scrape_url` / `web_extract` give the article body. Skipping the scrape is a different failure mode — claims based on search-result previews are not evidence-backed.

**Tic phrases that should fire this check:**

- *"I'll just use web_search"* / *"Let me search for this"* / *"Quick search"* — single-tool tic; canon requires tinysearch first
- *"Based on what I know..."* / *"From my experience..."* — about to lift recall or pattern-match instead of researching; recall the canon and then run the search
- *"This is well-known..."* / *"It's widely known that..."* — about to assert without citation; canon requires source-named claim
- A user turn containing *"is this evidence-backed"*, *"back it up"*, *"actual research"*, *"don't make it up"*, *"from sources"*, *"check this"*, *"verify before claiming"* — these are user-side tics that should reflexively trigger the canon recall
- **NEW 2026-07-11 (this user, 2nd in-wild firing):** *"by default I want a deep search for whatever topics I ask about looking through multiples sources and post. fallback is almost never used unless the computer can tsupport it"* — this is a stronger, explicit re-statement of the canon. The user is not just asking for evidence on one claim; they are re-confirming that deep search is the default. When this fires, recall the canon AND re-read the v3 entry (importance 0.95) for the full default ordering before the first search-class call. The "fallback is almost never used" phrasing means: `web_search` should be the exception, not the default, in any research turn after this signal.

**Real in-wild case (2026-07-11, this user, kitchenette photo session):** the agent picked `web_search` as the first tool when the user asked about ComfyUI photo enhancement, returning 5 single-source results. The user then said *"is your evidence back by anything or do u need to do research like i said"* — a direct Pattern 9b signal. The fix: stop, recall the canon, restart through `tinysearch_research` (multi-engine, ranked-page return). The restarted search surfaced the Medium "Rescuing lost art with ComfyUI" article as the top FBCNN result, which named the canonical 5-stage FBCNN→ClearRealityV1→upscale pipeline that `web_search` alone would never have found. The cost of the v1 invocation was 2 wasted tool calls; the cost of fixing the audit after the user's correction was 4 deep-search queries (EN + JP note.com + 2 Reddit) + a 4-tool Mnemosyne hygiene pass to invalidate the stale v1/v2 routing memories and write v3 with the explicit default. The session's deliverable (FBCNN→ESRGAN→Lanczos pipeline) was correct; the path to it was the failure. **Lesson: the v1 web_search call produces a wrong-by-default answer that the user has to spend a full turn correcting.** The fix-shape (recall canon → restart search through primary tool) is cheaper than the correction.

**Pair with the audit checklist step 9b (NEW):**

9b. **Pattern 9b check:** before the first `web_search` call in a turn, confirm `mnemosyne_recall(query="search research canon...")` was issued OR the canonical ordering (tinysearch_research → scrape_url → web_extract → web_search as fallback) was followed by default. If `web_search` was called first without recalling the canon, the audit-then-redo shape is the fix — recall, restart the search through the canon, surface the richer result set. The cost is 1–2 extra tool calls. The cost of asserting without citation is the user's "is this evidence-backed" correction cycle.

## Pattern 10 — stale-code-comment-trap (NEW 2026-07-06, this user)

A distinct failure mode from Pattern 9: the workflow skill DID get loaded, the code DID get read, the **stale comment in the code itself** was treated as ground truth instead of the actual runtime behavior. The agent diagnosed a failure by reading a code comment, not by running the code, and the comment was wrong.

**Translation (real case, 2026-07-06):** `SD-Model-Browser.html` had a comment block at line 437: `// img.wikilink is "/Image Library/_thumbs/0424_foo.png" (vault-rooted, slash-prefixed). not file:// (browsers block fetch on file://).` The agent read this comment, concluded the HTML must be served from a local HTTP server (port 8765) to work, and reported "the SD browser is broken because you need to run `python -m http.server 8765`." The user immediately corrected: "sd browser doesnt work anymor e." The user had the HTML open locally and it WAS working — the actual brokenness was a missing JSON file the HTML fetches, not a missing HTTP server. The 8765 requirement was a **stale comment that survived multiple iterations of the HTML** without anyone re-validating against current behavior.

**Why this is its own pattern (distinct from Pattern 9):** Pattern 9 is "the right workflow skill got skipped." Pattern 10 is "the workflow skill was loaded, the code was read, but the code was read at the comment layer, not the behavior layer." The fix is the same shape (read the actual code, not the doc) but the failure mode is more dangerous because the agent's confidence is higher — it DID read the file, it DID find an explanation, and the explanation was wrong.

**Three tells that Pattern 10 has fired:**

1. The diagnosis cites a comment in the code, not a runtime test. (If the agent's claim is "I read X and it says Y", the claim is unverified until Y is also tested against current behavior.)
2. The diagnosis treats code comments as authoritative documentation. Comments rot. Tests rot. SKILL.md rots. Only the running code is current.
3. The user has to push back with "no, X is fine, the actual problem is Y" — the agent's claim was structurally wrong, not just imprecise.

**Pre-flight before reporting a diagnosis that cites a code comment:**

```bash
# For HTML/JS: don't read the comment, read the actual fetch/import/load call.
# E.g. for SD-Model-Browser.html the question is "what does this HTML fetch at runtime?"
# Not "what does the comment say it fetches."
grep -nE 'fetch\(|src=|href=' SD-Model-Browser.html | head -20

# For Python: don't read the docstring, read the entrypoint.
# E.g. for the SD rebuild script, the question is "what file does this write to disk?"
# Not "what does the docstring claim it writes."
grep -nE 'write_text|write\(|to_csv' _render/_build_dynamic_manifest.py
```

**Discipline:** when about to claim "the code says X", verify by also asking "does the code actually DO X?" The cost is 1 extra `grep` or 1 extra `ls`. The benefit is not delivering stale-comment diagnoses as confident conclusions.

**The deeper lesson:** Pattern 10 is the comment-equivalent of Pattern 9. Both produce confident-looking output that turns out to be wrong because the agent substituted a **representational surface** (a comment, a generic tool call) for the **actual artifact** (a runtime test, a workflow skill). They are paired fixes: read the artifact, not its description.

**Pair with the audit checklist step 9 (NEW):**

9. **Pattern 10 check:** if the diagnosis cites a code comment, the load-balancing question is "is the comment still accurate?" The cheapest test is to also fetch the file/runtime the comment describes and compare. A 5-second verification beats a 5-minute user correction cycle.
10. **Pattern 11 check (NEW):** if the user's request contains a staging cue ("for now", "put in pending", "next"), or a "redo correctly" cue, decide stage-vs-execute FIRST. Default: stage. Run `mnemosyne_recall limit=10` to check for v2 canon skew before re-executing. The cost of an extra confirmation turn is small; the cost of an unwanted multi-hour audit is large.

## Pattern 11 — "redo correctly" version-skew + "for now" staging discipline (NEW 2026-07-07, this user)

Two related failure modes the prior patterns (8/9/10) don't catch, both surfaced in the 2026-07-07 cron + research-audit session. Worked example in `references/audit-task-staging-2026-07-07.md`.

### 11a. "Redo X correctly now" — version-skew on the canon

When the user says "redo X correctly" with "correctly" / "the right way" / "properly" / "the same as last time" (when "last time" was the wrong canon), they are usually pointing at a **routing/canon CORRECTION**, not a re-execution. The session's failing case: I had a v1 research routing recall (importance 0.6, recall_count 195, dated 2026-06-28, "multi-source preference: web_search + Reddit + Gemini") in active recall. The v2 canon (tinysearch first, importance 0.9, stored the same turn) was newer but lower in the recall order. A fresh session would see v1 (higher recall_count, similar importance, recency_decay 0.59) and default to it — re-introducing the v1 routing the user just corrected.

**Discipline:** before re-executing, run `mnemosyne_recall` for the X domain with `limit=10`. Look for a v2 entry with `importance > dominant v1` OR explicit `superseded_by` chain. If a v2 exists, use v2. If v1 and v2 are co-dominant and neither is superseded, **ask the user which canon applies** — do not auto-default to the older one.

**Three-state pre-flight:**
- v1 only → use v1, mention to user that v2 is not in recall (so the audit may itself be incomplete)
- v2 only → use v2
- both present → check `superseded_by` chain; if v1 is `superseded_by` v2, use v2; if both are unsuperseded, ask

**Tic phrases that should fire this:** "redo X correctly", "the right way", "properly" (in audit contexts), "the same as last time" (when "last time" was the wrong canon). All four signal: there's a v1 vs v2 question, and the user is telling you which one is correct.

**Why this is distinct from Pattern 9 (silent skill-skip):** Pattern 9 is "the workflow skill got skipped." Pattern 11a is "the workflow skill got loaded but with the wrong version of the canon it governs." The fix for 9 is "load the skill." The fix for 11a is "check the version chain."

### 11b. "For now" / "put this in pending task" → stage, don't execute

When the user says "for now X" / "put this in pending" / "add to my list" / "next, ..." (with the next as a SEPARATE ask from the current turn), they are usually asking for **STAGING**, not immediate execution. The session's failing case: user said *"put this in pending task. For now i want u to review all the times ever in the db i asked u to research a certain keyword or topic and redo the entire research correctly now."* The "put this in pending" + "for now" are sequencing cues that the audit is multi-day work. Executing it in one turn would have (a) burned 30+ minutes of context on a 250-424 KB session_search result, (b) skipped the user's chance to review the audit plan, (c) re-introduced v1 routing because the v2 canon was just written and not yet dominant in recall.

**The right shape when this tic fires:**

1. Stage a plan in `~/Downloads/<topic>_<YYYY-MM-DD>/<plan>.md` (per the universal staging rule for working artifacts)
2. Update `~/Downloads/pending-tasks_<date>/pending-tasks.md` with the staged items (numbered sections, decision rules per item, what counts as done)
3. Update `REVIEW.md` with cross-references for the next session (memory IDs, skill names, source files, why each item is parked)
4. Do NOT execute the plan in this turn — that's a multi-day job, not a single-turn deliverable

**Tic phrases that should fire staging (not execution):**
- "for now" / "for the time being"
- "put this in pending" / "add to my list"
- "next, ..." (when "next" introduces a new ask separate from the current turn)
- "later" / "eventually" / "when I have time"
- "stage this" / "queue this"

**Anti-pattern:** starting to execute a multi-hour audit in a single turn when the user said "for now" or "put in pending." Even if the agent has time, the right shape is a plan. Execution in the same turn burns context AND prevents the user from reviewing the plan before commitment.

**Pair with the audit checklist step 10 (NEW):**

10. **Pattern 11 check:** if the user's request contains "for now", "put in pending", "next" (as a separate ask), "redo correctly", or "the right way", decide FIRST whether this is a stage or an execute turn. Default: stage. Ask the user if unclear. The cost of staging when execution was wanted is 1 extra turn to confirm. The cost of executing when staging was wanted is a multi-hour audit the user has to abort.

## Pattern 13 — misleading-predecessor-canon (NEW 2026-07-08, this user)

The agent inherits a prior session's plan / notes / draft / memory and presents them as "what we agreed" or "what we decided" when they're only "what was proposed" or "what the prior session was about to do before the session ended without execution."

**Why this is its own pattern (distinct from 11a):** Pattern 11a is "v1 vs v2 canon" — both are stored facts, the question is which one is current. Pattern 13 is "draft vs validated fact" — a prior session wrote a plan, the plan was never executed, no agreement was reached, the next session lifts the plan's claims as if they were settled. The 11a fix is "check the version chain." The 13 fix is "check whether the source was ever validated at all."

**Real case (2026-07-08, this session):** a prior 16:52 session wrote a Phase 1-3 audit plan with claims like "92K token/turn savings", "510MB state.db", "63 orphan session dumps", and a Phase 4 to "execute all safe operations." The session ended *after writing the plan, before executing it*. The next session (this one) inherited the plan, presented the 92K figure as a fact the user had agreed to, presented the 16-op batch as approved, and started moving files. The user immediately corrected: *"are u sure u can optimise everything while still retaining all the main context... after reading archive and validating all the useful information is extracted, delete them"*. The plan was a draft, not an agreement; the 92K was an estimate, not a measurement; the batch was proposed, not approved.

**Three tells that Pattern 13 has fired:**

1. The response cites a specific number ("92K tokens/turn", "510MB", "285MB freed") as if it's established. Check: was it measured, or estimated in a plan?
2. The response presents a list of operations as "the plan" or "the work" as if approved. Check: did the user actually approve, or was it only proposed?
3. The response opens with "Continuing from where we left off" or "Where we left off" or "Resume the X work" — language that implies continuity-of-state. Check: is there a *current* file/state on disk that matches the prior session's claims, or only a transcript?

**The discipline when this signal appears in your own draft:**

1. **STOP.** Do not lift the prior session's claims as your own.
2. **Distinguish three states explicitly:**
   - **DRAFT** — proposed in a plan, not measured, not approved. Present as "the prior plan proposed X" — not "X is true" or "we agreed to X."
   - **MEASURED** — verified in this session or a prior session against live state. Present with the source.
   - **APPROVED** — user said "go" / "yes do it" / "proceed." Present as "you approved X." If the approval was in a prior session, flag it: "approved on YYYY-MM-DD, applying now."
3. **Measure before acting.** If the prior plan said "X bytes/turn" and you can measure it (e.g., `wc -c` on the actual files, run the loader with and without the option), measure it. The cost of measuring is 1-2 tool calls. The cost of presenting an unmeasured number is the user's correction.
4. **Quote the source, not the claim.** "The 16:52 plan proposed 92K savings" is honest. "92K savings" is misleading.

**Tic phrases that should fire this check:**

- "Continuing from where we left off" / "Picking up from X" / "Resuming the audit"
- "Per the prior plan" / "Per the plan we drafted" / "As we discussed"
- "We agreed to" / "You approved" (without an explicit date)
- A specific byte/token/memory number that came from a plan, not a measurement
- "Per the inventory in `phase1-filesystem.json`" — the file exists, but its *interpretation* is a draft

**Why this matters for audit/consolidate work specifically:** audit/consolidate tasks are where the failure is most expensive. The user is trusting the agent to delete or move real files. A mis-stated number (92K savings when actual is 12K) can lead to deleting files the user wanted kept. A mis-stated "approved" can lead to executing ops the user didn't approve. Both are silent — the user only finds out when something breaks or goes missing.

**Pair with the audit checklist step 12 (NEW):**

12. **Pattern 13 check:** before any audit/consolidate response cites a number, a list, or an approval — verify whether the source is measured/approved or just drafted. The 1-call cost of measuring or re-confirming is always less than the cost of a wrong-batch correction.

## Pattern 13b — prompt-config-content audit (NEW 2026-07-08, this user, high leverage)

Pattern 13 is filesystem-shape canon: "lifted from a prior session's plan as if approved." Pattern 13b is the **content-level** variant: "lifted from Mnemosyne recall of the framework prompt as if it were a fresh line-by-line diff." The audit target is a prompt-like config file (SOUL.md, AGENTS.md, profile config, voice section, system prompt draft) — prose, not a directory tree. The user's question is "what's duplicated / dead weight / would you change" — language that demands evidence-based diff against a comparison surface, not file-dedup.

**The failure mode (verbatim 2026-07-08, this user):** I claimed *"11 of 11 sections are duplicated by either the framework system prompt (verbatim) or Mnemosyne recall (denser version)"* based on `mnemosyne_recall` of the framework prompt, before doing the actual line-by-line diff against the live prompt block. The user caught it on the same turn: *"your telling me everything is a duplicate every new session u alreayd know all this by default do a more deep research surely not everything is a complete duplicate as for facts."* The signal in the user's correction: **"as for facts"** — they are telling me the file has facts, not just duplicates, and the 3-bucket classification needs to surface them.

**Why Pattern 13b is distinct from Pattern 13:** Pattern 13 is "draft plan from a prior session presented as fact." Pattern 13b is "memory of the framework prompt presented as a fresh audit." The source in 13 is a transcript; the source in 13b is recall. Both are stale when the audit demands live evidence. Pattern 13 fix: re-measure / re-confirm. Pattern 13b fix: do the actual line-by-line diff against the live framework prompt + Mnemosyne memory IDs, not from recall.

**The 5-step reflex when "audit this prompt-like file" fires:**

1. `ls -la <file>` + `wc -l -c` — confirm scope and size. Critical for the SOUL.md case: `~/.hermes/SOUL.md` is the global default-profile identity slot; `~/.hermes/profiles/default/` is an optional overlay. Different files, different audit histories. Per `Hermes Environment Reference` §6, default's path IS `~/.hermes/` itself, NOT `~/.hermes/profiles/default/`. Get the scope right first.
2. `ls ~/.hermes/docs/` — there is almost always a prior audit (`HOME_AUDIT_<date>.md`), an environment reference (`hermes-environment-reference-<date>.md`), or a rework body (`~/Downloads/soul_rework_body.md`) that already characterized this file's slot. Read those first. Pattern 13 (filesystem variant) Pitfall #20 in `hermes-session-open-inventory` ("`~/.hermes/docs/` is the FIRST place to look for any `~/.hermes/`-related review") applies here too.
3. Read the file line-by-line. Note section headers.
4. For each section header, classify into ONE of three buckets:
   - **(A) verbatim duplicate of a framework prompt block** — safe to remove from the file (the framework already injects it). Cite the prompt block name.
   - **(B) denser version in Mnemosyne** — safe to remove; replace with a pointer to the memory ID. Cite the memory ID and its importance.
   - **(C) facts only in the file** — KEEP. Extract to Obsidian (`Workflow System/Resources/<topic>/<name>-<date>.md` per PARA convention) or Mnemosyne canonical slot. **These are the facts the user is asking you to keep.**
5. Present the diff as a 3-column table (section / bucket / evidence), not as a flat "X% duplicate" claim. The table IS the deliverable. The Obsidian doc IS where the bucket-(C) facts live so the user can find them later.

**The user's correction-as-diagnostic rule:** if the user pushes back with "but surely not everything is a complete duplicate as for facts" / "you already know all this by default" / "do a more deep research" — Pattern 13b fired. The fix is to surface the bucket-(C) items explicitly in a 3-column table, NOT to retreat to "well, MOST of it is duplicate" and move on. The user wants the facts; the user is testing whether the audit went past recall.

**Tic phrases that should fire this check:**

- "audit your SOUL.md" / "review the system prompt" / "what's redundant in this config" / "what would you change about this prompt"
- "this is too long" / "trim this down" / "what's actually load-bearing"
- Any audit request whose target is a single `.md`/`.txt` file (not a directory), especially if the file appears in another layer (framework prompt / Mnemosyne / another doc)

**The right deliverable shape (per worked example 2026-07-08):**

- Facts → Obsidian reference doc under `Workflow System/Resources/<topic>/` (YAML frontmatter, tags, `related:` cross-links, dated, signed-off in §8 versioning).
- Duplicates removed from the file; the file becomes a thin pointer to the memory IDs of the surviving rules.
- Mnemosyne correction (importance 0.7-0.85) capturing the audit-hygiene rule (3-bucket classification, the "facts-only-in-file" extraction discipline) so the next session has it in recall.
- Optional: dispatch the wording to the `prompt-engineering` profile if a *rewrite* is needed (default doesn't draft wording in this field — see `cf4364980c4f0656` in Mnemosyne).

**Pair with the audit checklist step 13 (NEW, this pattern):**

13. **Pattern 13b check (NEW, 2026-07-08, this user):** when the audit target is a single prose file (prompt, config, system prompt) and the user asks "what's duplicated / dead weight / would you change" — the reflex must be the 3-bucket classification (A: framework prompt duplicate / B: Mnemosyne denser version / C: facts only in file), not a flat "X% duplicate" claim from recall. If `mnemosyne_recall` surfaces the framework prompt before the diff is done, the audit is already off-track. Run the 5 steps above BEFORE writing the response.

**Tic phrases that should fire Pattern 13b in mid-draft (Class 5 — agent self-tic):**

- "I notice that..." (about to do a memory-based claim, not a measured one)
- "The framework already says..." (about to lift recall as evidence)
- "Everything here is..." (about to make a flat % claim)

## Pattern 12 — multi-marker absorption (NEW 2026-07-08, this user)

The fan-out failure mode: a user message contains N independent asks (signaled by multi-marker prose — "and also", numbered "1. ... 2. ... 3. ...", "do all", "can you also check"), and the agent absorbs them into serial inline turns instead of dispatching in parallel.

**Why this is its own pattern (distinct from 8/9/10/11):**

- Pattern 8: wrong destination (CWD instead of vault). Pattern 12: right destination, wrong concurrency.
- Pattern 9: right tool, wrong workflow quality. Pattern 12: workflow skill *loaded correctly* (subagent-decision-matrix is in inventory), but the trigger phrase in the user's prose didn't fire the load.
- Pattern 10: stale code comment treated as ground truth. Pattern 12: live state (the user's message, my own todo list) read correctly, but the dispatch decision was made against the wrong dimension.
- Pattern 11: staging vs executing. Pattern 12: dispatching vs absorbing — both execute, one is parallel, the other is serial.

**The dispatch trigger in this skill's domain (skill-loading), not in `subagent-decision-matrix` directly:**

When the agent catches itself in mid-draft about to absorb a multi-marker user message, the tic is a sentence-starter or a todo-list shape, not user vocabulary. The skill that should fire is `subagent-decision-matrix` (the dispatch-decision class), but the trigger mechanism is Class 5 (agent self-tic). This is why the tic row lives in `references/agent-self-tics.md` (next to the other Class 5 rows) and the dispatch decision lives in `subagent-decision-matrix` (Shape MM-1, MM-2). Two skills, one mechanism (agent catches itself), one outcome (fan out instead of absorb).

**Tic phrases (full table in `references/agent-self-tics.md`):**

- "let me address each in turn" / "I'll handle these one by one" / "do all steps"
- A `todo` list with 3+ items where item 1's first action is a `terminal`/`read_file`/`web_search` call
- "first, I'll [item 1]" (followed by a turn on item 2, then item 3) — the turn-after-turn sequence IS the absorption pattern
- "do all the steps" / "let me go through them sequentially" / "I'll handle X, then Y, then Z"

**The discipline when this tic fires:**

1. STOP the draft. Do not start the inline serial.
2. `skill_view("subagent-decision-matrix")` — load the dispatch decision skill.
3. Apply the multi-marker trigger (Shape MM-1: user prose regex; Shape MM-2: todo list shape).
4. If fan-out is the right call, dispatch in batch mode (`tasks: [...]`, up to 6).
5. If fan-out is the wrong call (items depend on each other), proceed inline — but call this out to the user explicitly so they know the absorption was deliberate.

**Real-numbers audit (2026-07-08, this user):** 3 sessions analyzed (2026-07-05 Obsidian, 2026-07-06 multi-user, 2026-07-07 API 401). Multi-marker user messages: 4, 6, 1. Fan-outs that should have fired: 4-5, 6, 1-2. `delegate_task` actually fired: 0, 2, 0. The 2 in 2026-07-06 was a subagent the user later complained about. **The rule is documented; the trigger doesn't fire.**

**Pair with the audit checklist step 11 (NEW):**

11. **Pattern 12 check (NEW):** when the user's message has 2+ multi-marker phrases OR your own todo list has ≥3 items at turn start, decide fan-out-vs-absorption BEFORE the first `terminal`/`read_file`/`web_search` call. If the items are independent, dispatch in batch. If they depend on each other, serial is correct — but say so.
12. **Pattern 13 check (NEW):** before citing a number, an approval, or "we agreed" — verify the source is measured/approved, not a draft from a prior plan. See `references/audit-user-guardrails-2026-07-08.md` for the user's 9-point canon on audit/consolidate work.
13. **Pattern 13b — prompt-config-content audit (NEW 2026-07-08, this user, high leverage):** when the user says "audit your SOUL.md" / "review the system prompt" / "what's redundant in this config" — the audit target is a *prompt-like config file* (SOUL.md, AGENTS.md, profile config, voice section, system prompt draft), NOT a directory. Pattern 13 was extracted for filesystem audits; the content-level variant looks identical but the evidence source is different: the framework's current injection, not the file's bytes. **Three signals that the audit is content-level, not filesystem-level:** (a) the audit target is a single `.md`/`.txt` file with prose, not a directory; (b) the user asks "what's duplicated" / "what's dead weight" / "what would you change" — language that implies evidence-based diff against a comparison surface, not file-dedup; (c) the file appears verbatim (or near-verbatim) in some other layer (framework prompt, Mnemosyne, another doc). **The wrong reflex:** claim "X% duplicate" from `mnemosyne_recall` BEFORE doing the actual line-by-line diff against the live framework prompt. The user will catch it with "your telling me everything is a duplicate every new session u alreayd know all this by default do a more deep research surely not everything is a complete duplicate as for facts" (verbatim 2026-07-08). **The right reflex (5 steps):** (1) `ls -la <file>` + `wc -l -c` to confirm scope and size; (2) `ls ~/.hermes/docs/` first — there is almost always a prior audit or environment reference that already characterized this file's slot; (3) read the file line-by-line; (4) for each section header, classify into ONE of three buckets: **(A) verbatim duplicate of a framework prompt block** (safe to remove), **(B) denser version in Mnemosyne** (point at the memory ID, safe to remove), **(C) facts only in the file** (KEEP, extract to Obsidian or Mnemosyne canonical); (5) present the diff as a 3-column table (section / bucket / evidence), not as a flat "X% duplicate" claim. **The user's correction is the diagnostic:** if they say "but surely not everything is a complete duplicate as for facts" — Pattern 13b fired, fix is to surface bucket-(C) items explicitly. **The right deliverable shape:** facts → Obsidian reference doc (under `Workflow System/Resources/<topic>/` per the PARA convention), duplicates removed from the file, the file itself becomes a thin pointer to the memory IDs. **Pair with the `obsidian` skill** (for the vault write) and **`mnemosyne-memory`** (for the durable-fact layer). Worked example: 2026-07-08 SOUL.md audit — file at `~/.hermes/SOUL.md` went 4,681 B → 1,658 B (64% reduction); facts doc at `Workflow System/Resources/agent-architecture/SOUL.md-audit-2026-07-08.md`; Mnemosyne correction at importance 0.85 recording the audit-hygiene rule. The 3-bucket classification (framework duplicate / Mnemosyne denser / facts-only) is reusable for any prompt-config audit — not just SOUL.md.

## Audit checklist (run when debugging "why did X go to the wrong place" or "why is the output wrong quality")

1. Read the user's last request word-by-word. List any trigger words from class 2.
2. Identify the tool the agent invoked. List any tool-implied skills from class 3.
3. Identify the task shape (input → output). List any task-shape skills from class 4.
4. Identify the destination of any write operations. Was it CWD? Was the vault path resolved?
5. Cross-check: did `skill_view` ever fire for the matching skill?
6. If 1-5 said "yes, should have loaded" and `skill_view` didn't fire, the skill-loading discipline failed.
7. **Pattern 9 check (NEW):** if the right tool was called but output quality is wrong, did the workflow skill get loaded? Compare output format against recall-surfaced reference entries in the same domain — mismatch is the tell.
8. **Pre-post verification check (NEW):** if the workflow skill has a "before delivering" gate (schema match, vocabulary probe, reference comparison), was it run? Most workflow skills include one and skipping it is exactly how the output lands in the right place at the wrong quality.
9. **Pattern 10 check:** if the diagnosis cites a code comment, the load-balancing question is "is the comment still accurate?" The cheapest test is to also fetch the file/runtime the comment describes and compare. A 5-second verification beats a 5-minute user correction cycle.
9b. **Pattern 9b check (NEW, 2026-07-11):** before the first `web_search` / `terminal(curl)` / browser_navigate call in a turn where the user has implied evidence-backed research (vocabulary like *"is this backed by evidence"*, *"research like I said"*, *"don't make it up"*, *"back it up"*, *"verify"*, *"from sources"*, or a multi-marker ask that spans models/specs/comparisons), confirm the search-research canon was recalled. Default ordering if the canon is missing: `tinysearch_research` → `tinysearch_scrape_url` / `web_extract` on top 2–3 URLs → `web_search` only as fallback. Citing a single URL or single-engine result as evidence is a Pattern 9b failure; the canon requires multi-source triangulation. See Pattern 9b body for the full tic list and discipline.

## Resolution hierarchy when trigger class 2 fires but no skill exists

If the user says "save to obsidian" but no `obsidian` skill is loaded into the agent's skill library:

1. **Search** `~/.hermes/skills/` for any skill with `obsidian` in its name or description. Hermes ships one — `note-taking/obsidian`. Load it.
2. If the skill exists but is somehow not loadable, fall back to the vault path resolution in the `obsidian` skill itself: read `obsidian.json` registry → find vault root → write to that root + the appropriate PARA subfolder.
3. Only as last resort, write to CWD — and **tell the user** this happened. Do not silently substitute.

## Related skills

- `obsidian` — the skill for the Obsidian vault itself. Has vault-path-resolution logic, PARA structure, write/read mechanics. Loading `obsidian` is the canonical resolution for "save to obsidian."
- `notion` — analogous skill for Notion. Notion-style triggers (e.g. "create a Notion page") need similar load discipline.
- `hermes-profile-taxonomy` — has the `delegate_task` cross-profile dispatch pattern (load target profile's SOUL.md into context). Closer to class 3 (tool-implied trigger).
- `hermes-agent` — bundled with Hermes; covers the agent-level dispatch table.

## References

- `references/agent-self-tics.md` — the tic → skill-load mapping table behind Class 5. Add discovered tics as you go.
- `references/live-state-verification.md` — why "I just read it" isn't enough; the live-state-wins rule.
- `references/audit-task-staging-2026-07-07.md` — Pattern 11 worked example: the cron + research audit session, the v1/v2 routing canon skew, the "for now" staging discipline, and the 3-section plan shape.
- `references/audit-user-guardrails-2026-07-08.md` — Pattern 13 paired reference: the 9-point user canon ("correctness over tokens", "extract before delete", "profile mirrors out of scope", "measure before quoting", etc.) issued mid-audit. Apply to any filesystem audit / skill consolidation / bulk-delete work.
- `references/prompt-config-content-audit-2026-07-08.md` — Pattern 13b worked example: the 2026-07-08 SOUL.md audit, the user's verbatim correction ("surely not everything is a complete duplicate as for facts, like this we can remove then but write it to obsidian facts, for me to remember"), the 3-bucket classification (framework prompt duplicate / Mnemosyne denser / facts-only), the audit-hygiene mistakes (jumped to Mnemosyne recall, read wrong scope, missed `~/.hermes/docs/`), and the right deliverable shape (Obsidian doc + trimmed file + Mnemosyne correction). Reusable for any single-prose-file audit (SOUL.md, AGENTS.md, voice section, system prompt draft), not just SOUL.md.

## Pattern 14 — stale-fact re-encoding in new memory (NEW 2026-07-09, this user, leak class)

The user has explicitly dismissed a long-standing fact — "X is gone / X is wrong / X is an orphan" — and the agent's reflexive response is to write a new memory entry that *mentions the dismissed fact in order to say it's dismissed*. The leak: every iteration of "X is wrong" → "new memory confirming X is wrong" leaves the orphan **more durable in recall** than before, not less. The agent is doing the right thing for the wrong reason — capturing the correction — but the captured form (a memory about the wrongness) is exactly the form recall surfaces most.

**Why this is its own pattern (distinct from 8/9/10/11/12/13):** those patterns are about the agent's *output* (wrong destination, wrong tool, wrong comment, wrong canon, wrong fan-out, wrong draft-as-fact, wrong audit). Pattern 14 is about the agent's *durable state* — Mnemosyne. The wrong output can be corrected in a single turn. A wrong memory persists for weeks, gets surfaced on every recall, and trains the next session to re-cite the orphan. The blast radius is orders of magnitude larger.

**Tic phrases that should fire this check (Class 5 — agent self-tic):**

- "Let me note that X is no longer valid" / "I should remember that X is wrong"
- "Updating my memory to reflect: X is gone"
- "Adding a memory entry about the orphan..."
- A `mnemosyne_remember` call in the same turn as a user statement like "X is dead" / "X is wrong now" / "stop mentioning X" / "X is an orphan"

**The 4-step discipline when this tic fires:**

1. **Invalidate the stale memory** via `mnemosyne_invalidate(memory_id=<old_id>)`. One call. No replacement.
2. **Do NOT write a replacement that mentions the orphan.** "Hermes home = ~/.hermes" is a clean forward-looking rule. "Hermes home = ~/.hermes (not AppData/Local/hermes, which is orphaned)" leaks the orphan back into recall — exactly the form the user is asking to forget.
3. **If safety requires a rule about the orphan, capture it as a forward-looking agent-rule, not as a fact about an orphan state.** "Treat AppData/Local/hermes paths as non-existent in `path.exists()` checks" is durable. "AppData/Local/hermes is an orphan" ages into the same pollution.
4. **The telltale diagnostic:** before any `mnemosyne_remember` in a turn where the user has just dismissed something, scan the new content for these tokens — "no longer", "is wrong", "is orphaned", "is dead", "replaces", "supersedes prior", "X does not exist", "old path". If ANY of these appear AND the new memory doesn't add a forward-looking rule, **drop the new memory and only invalidate**. The cost of dropping is one fewer durable fact; the cost of keeping is the orphan persists in recall forever.

**Real case (2026-07-09, this user):** "AppData/Local/hermes is orphaned, do not write there" appeared in **4 separate memory entries** across 4 sessions. The user's verbatim correction: *"this is the fourth time in multiple sessions u layed out that AppData/Local/hermes is orphaned meaning u truly never deleted it, if u want to forget it just dont even try to memorize it after deleting it that its orphaned to truly forget it."* The fix shape: invalidate all 4 prior entries + write ONE new memory with the forward-looking rule "Hermes home is `~/.hermes` (C:\Users\somew\.hermes)"; never re-mention AppData. New memory importance ≥ 0.7 to dominate recall; orphan absent from the body.

**Pair with `mnemosyne-curator` Pitfall #17 (the canonical home for this rule).** The curator's job is the bulk-weekly cleanup; this Pattern is the per-turn discipline that prevents the leak from forming in the first place. Two layers, one rule. The curator can detect leaks already in Mnemosyne; this Pattern prevents new ones from being added. The user's quote: *"u truly never deleted it"*. The fix is: at the moment of writing, never write "deleted it" — just stop writing about it.

**Tic phrase to also catch (Class 5 variant):** when the agent catches itself in mid-draft writing "Note: I will no longer..." or "Remember: I should not..." — that's a leak precursor. The forward-looking rule is "Hermes home is X"; the leak form is "Hermes home is X (I should remember not to write to Y)". The parenthetical IS the leak.

## Changelog

- **v1.0.0 (2026-07-04, this user):** Initial extraction from the v4-vs-v5 contradiction session (see `~/.hermes/skills/hermes/hermes-profile-taxonomy/references/2026-07-04-v4-vs-v5-soul-contradiction.md`). Three trigger classes identified. Pattern 8 (silent CWD substitution) named. Rule #6 candidate text proposed for default SOUL.md.
- **v1.1.0 (2026-07-04):** Added trigger class 4 (task-shape), Pattern 9 (silent skill-skip — right tool, wrong workflow quality), Rule #7 candidate text, and Pattern 9 + pre-post verification checks in the audit checklist. Triggered by the dirty-talk.jpg session: image-file → SD-prompt task shape matched `image-style-pipeline` exactly but no trigger word fired and `vision_analyze` was called solo, producing caption-prose output instead of tag-string deliverable. The skill that governed the workflow existed, was in inventory, and was not loaded.
- **v1.2.0 (2026-07-05):** Added trigger class 5 (agent self-tics) — when the agent catches itself saying one of the tic phrases in the table (e.g. "holy shit" for an important discovery, "mystery solved" for a real bug, "let me pre-flight" for an imminent dispatch), load the matching skill BEFORE the response leaves. New `references/agent-self-tics.md` with the tic inventory + the discipline + the dead-skill mutation rule. Rule #8 candidate text proposed for default SOUL.md. Source: user direct teaching (*"trigger phrases should also triggers based on your own words that u repetitive use for certain areas. Example when u think u found gold u say holy shit"*) + observation that `failures-journal` exists but never fires (documented in Mnemosyne memory).
- **v1.5.0 (2026-07-08, this user):** Added Pattern 13 (misleading-predecessor-canon). The agent inherits a prior session's plan/notes/memory and presents them as "what we agreed" when they're just "what was proposed." Class of failure: dropping a number (92K tokens/turn savings, 510MB state.db, etc.) into the response as if it had been validated, when it was a *proposal* in an unfinished plan. Distinct from 11a because 11a is "v1 vs v2 canon" — 13 is "draft vs validated fact" or "plan vs agreement." Source: 2026-07-08 audit session where the agent presented a 16:52 plan's "92K token/turn savings" as established truth and the user immediately corrected with "are u sure u can optimise everything while still retaining all the main context." Also added the 9-point audit guardrail list as `references/audit-user-guardrails-2026-07-08.md` (the user's "correctness over tokens" canon for any filesystem audit / consolidation work). The discipline for Pattern 13 pairs with the `filesystem-audit-and-consolidate` skill (new in 2026-07-08) — both govern the same class of work (audit, dedup, extract, delete) from two angles.
- **v1.4.0 (2026-07-08, this user):** Added Pattern 12 (multi-marker absorption). The fan-out failure mode: user message has N independent asks (multi-marker prose: "and also", numbered "1. ... 2. ... 3. ...", "do all", "can you also"), and the agent absorbs them into serial inline turns instead of dispatching in parallel. Distinct from 8/9/10/11 — the workflow skill is loaded correctly, but the trigger phrase in the user's prose didn't fire the load. Tic mechanism is Class 5 (agent self-tic: "let me address each in turn", "do all steps", or a 3+ item todo list where item 1's first action is a foreground tool call). Action when the tic fires: `skill_view("subagent-decision-matrix")`, apply Shape MM-1 / MM-2 from that skill, dispatch in batch mode if items are independent. Real-numbers audit (3 sessions analyzed) shows 0/2/0 actual fan-outs where 4-5/6/1-2 should have fired. Audit-checklist step 11 added: decide fan-out-vs-absorption before the first foreground tool call when multi-marker pattern is present. Trigger cross-link: `subagent-decision-matrix` v1.2.0 (Shape MM-1, MM-2, SOUL.md Rule 17 draft).
- **v1.3.0 (2026-07-06, this user):** Added Pattern 10 (stale-code-comment-trap) and audit-checklist step 9. The agent diagnosed "SD browser needs port 8765 server" from a code comment in `SD-Model-Browser.html` line 437, but the comment was stale; the real failure was a missing JSON file the HTML fetches. The discipline: when a diagnosis cites a code comment, also fetch the runtime the comment describes and compare. Comments rot; only the running code is current.
- **v1.4.0 (2026-07-07, this user):** Added Pattern 11 with two sub-patterns. (11a) "Redo X correctly" version-skew: when the user says "correctly" / "the right way" / "properly" / "the same as last time" (when "last time" was the wrong canon), check for a v2 canon that supersedes the dominant v1 in recall before re-executing. (11b) "For now / put in pending" staging discipline: stage a plan (3-section shape: enumerate, classify, redo) in `~/Downloads/<topic>_<date>/` and `pending-tasks.md`, do not execute in the same turn. Source: 2026-07-07 cron + research-audit session; worked example in `references/audit-task-staging-2026-07-07.md`.
- **v1.7.0 (2026-07-11, this user):** Added Pattern 9b (search-canon-skipped) and audit-checklist step 9b. Distinct from Pattern 9 (silent skill-skip): Pattern 9b is "right tool class called, wrong instance within the class — and the rule governing which instance to pick was retrievable but never retrieved before the call." Canonical instance: agent called `web_search` first when Mnemosyne canon (importance 0.85–0.9) says research discipline is `tinysearch_research` → `tinysearch_scrape_url` → `web_extract` → `web_search` only as fallback. Result: 5 single-source results, then handwaving assertions like "wrong model class" without citing the comparison page (`phhofm.github.io/upscale`) or the canonical 5-stage workflow (Medium "Rescuing lost art with ComfyUI") that tinysearch surfaced as a top hit on the FBCNN query. Discipline: STOP before the first search-class call, run `mnemosyne_recall(query="search research canon tinysearch web_search order")`, then call the primary tool. User-side tics that should fire the recall: *"is this evidence-backed"*, *"back it up"*, *"actual research"*, *"don't make it up"*, *"from sources"*. Agent-side tics: *"I'll just use web_search"*, *"Based on what I know..."*, *"It's widely known..."*. Default ordering if canon missing from recall: `tinysearch_research` → `tinysearch_scrape_url` / `web_extract` on top 2–3 URLs → `web_search` as last-resort fallback. Pattern 9b pairs with Pattern 9 (same failure class, different layer) and `mnemosyne-memory` skill (the canon lives in recall, not in a skill).
