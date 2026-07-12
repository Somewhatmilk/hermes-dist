---
name: information-validation
uses: [multi-source-research-tactics]
description: "Cross-reference methodology: validate claims from multiple independent sources, search for concrete data, question 'best'/'must have' assertions, and apply critical thinking universally. ALSO fires for proactive research without being asked — when the user asks 'what's best for X' or makes a comparison between tooling/models/approaches and the agent has no concrete evidence, research BEFORE answering, not after."
version: 1.2.0
author: Hermes Agent
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, methodology, validation, critical-thinking, cross-reference]

---# Information Validation & Cross-Reference Methodology

A systematic approach to validating information that prevents single-source bias and produces well-grounded answers. Apply this methodology to **every research task**, regardless of domain — games, tech, products, news, comparisons, etc.

## CRITICAL: User Communication Preferences  

**This was the most frequently corrected behavior. Read this before every response.**  

The user wants **result-first, direct communication**. Violations of these rules are the #1 source of frustration:  

- **Do NOT narrate your process.** Never say "Let me check...", "I will now...", "Here's what I found after analyzing..." — just do the work and present findings. Every introductory phrase is wasted token.  
- **Do NOT recap your reasoning.** If asked for data, give the data. If asked for analysis, give the conclusion with brief supporting evidence. Do not walk through intermediate thoughts.  
- **Do NOT explain corrections at length.** The user corrects you? Acknowledge in one line and fix the approach. Do not re-state what went wrong in detail.  
- **Cut ALL fluff, keep ALL substance.** No transitions about what you're about to do. No meta-commentary. Deliver the answer first.  
- **One-line answers are fine** if they answer the question. Dense over verbose.  
- **When something is NOT possible, say so directly.** Do not propose workarounds or alternatives unless you can articulate WHY they are better after weighing pros and cons. The user explicitly wants honesty over pleasing: "say when something is not possible realistic instead of trying to please me or give a better approach but only if it indeed is better after weighing the pros and cons." A "this is not possible" with reason is better than a weak alternative.  
- **Weigh pros and cons before suggesting alternatives.** If the primary approach fails, only suggest an alternative if you can list specific trade-offs (cost, time, effort, reliability). Do not offer mitigation just to fill space.  

If you would start a response with "Let me," "I'll," "I want to," "I need to," "First I'll" — STOP. Those are all narration. Just do it silently. The user should never see your internal reasoning steps — only the output.

## Core Principles

1. **Never trust a single opinion** — every source has bias, blind spots, or incomplete information
2. **Validate from different world-view perspectives** — seek sources from different communities, platforms, and cultural contexts
3. **Source from separate, independent areas** — don't cite three sources that all quote the same original
4. **Test before assuming** — when the user says something works and you think it doesn't, try it FIRST before explaining why not. The user's domain knowledge beats your assumptions about their environment.
5. **Check the system before concluding "no access"** — git credentials, SSH keys, env vars, token files. They often exist; you just haven't looked yet.
6. **Question "best" / "must have" / "top tier" claims** — always ask: *why* is it best? For whom? Under what conditions? What's the trade-off?
7. **Search for concrete data** — don't assume or rely on memory for numbers (currencies, drop rates, pull counts, prices, breakpoints). Look them up.
8. **Proactive research is the default when claiming tooling/model comparisons (NEW 2026-07-10).** When the user asks "what's the best X for Y" or compares approaches the agent has not personally tested and has no concrete evidence for, the user expects the agent to **research BEFORE answering**, not after. Verbatim signal: *"whenever u dont have a concrete, evidence backed answer u do researc without me telling u to do, on what to research refine your finding to me and ill tell u how to re-iterate and improve the steps along the way."* The corollary: don't anchor on the prior turn's model family when the new image/task is a different domain — verify with `vision_analyze` (or equivalent first-hand probe) before naming a model. Carrying forward "we were just talking about Illustrious, so SDXL/Illustrious applies" is exactly the failure mode this rule prevents.

> **Overlap note:** This skill overlaps with **`multi-source-research-tactics`** (devops category). The other skill covers the specific research workflow (finding sources, checking tiers, community pulse). The curator should consider consolidation — for now, both exist with complementary content. This skill focuses on the critical thinking methodology and communication style; the other focuses on the research workflow steps.

## Step-by-Step Process

### 1. Context Gathering
When the user references something from a past discussion, use `session_search` to retrieve the last 10-20 messages from both the front and back of the relevant section. This gives the full picture — goal, discussion, and resolution — without relying on memory or asking the user to repeat themselves.

**Key rule: grab the surrounding conversation window** — not just the exact match line. The context before and after often contains important framing, corrections, and conclusions.

### 2. Multi-Source Research
For any factual claim or recommendation, gather from at least 2-3 independent sources:

| Source Type | Examples | When to Use |
|-------------|----------|-------------|
| Official docs | Game wikis, API docs, product pages | Ground truth for mechanics, specs, pricing |
| Community hubs | Discord, Reddit, forums | Real-world experience, meta shifts, hidden quirks |
| Content creators | YouTube guides, tier list spreadsheets | Curated analysis, but verify their methodology |
| Aggregators | Tier lists, comparison sites | Quick overview, but verify individual claims |
| Direct testing | Your own terminal/browser | When feasible — nothing beats empirical verification |

### 3. Cross-Reference Pattern
For each claim you encounter:
1. **Identify the claim** — "Character X is S-tier", "Tool Y is the best"
2. **Find the reasoning** — Why do they say that? (specific numbers, roles, synergies)
3. **Find a counter-source** — Search for "X weaknesses", "X vs Y comparison", "when NOT to use X"
4. **Synthesize** — Under what conditions is the claim true? What are the trade-offs?

### 4. Concrete Data Over Assumption
Never assume numerical values. Always search for:
- Currency earnings per chapter/level/activity
- Pull/roll counts and pity systems
- Dupe/duplication breakpoints (how many copies matter before diminishing returns)
- Upgrade material costs
- Time-to-farm estimates

### 5. Questioning "Best" Claims
When someone says something is "the best" or "must have", ask:
- **What specific role does it fill?** (DPS, support, utility, enabler)
- **How many dupes/copies are needed before it performs?** (E0 vs E3 vs max — the gap matters)
- **What's the opportunity cost?** (What else could you spend those resources on?)
- **Is it meta-dependent?** (Does it need specific teammates, gear, or content type?)
- **Is the source incentivized?** (Affiliate links, creator bias, hype cycle)

### 6. Answer-Question Fit Validation

When someone provides an answer, validate that the answer actually addresses the question asked — not just that the information is factually correct. This is a distinct skill from source validation.

**Common forms of answer mismatch:**
- **Technical answer to philosophical question** — User asks "who am I / what's my style?" and gets block weights, model URLs, or technical procedures. The answer is correct but addresses a different question.
- **Procedural answer to identity question** — "I don't know what I want" met with "here's a workflow." The workflow helps execute, not decide.
- **Avoidance through specificity** — Giving detailed advice on a minor sub-topic to dodge the core question.
- **Authority deflection** — "I can answer because I can draw" when the question is about the asker, not the answerer.
- **Externalization** — "Send me 5-10 images and I'll tell you" moves the discovery burden to the asker rather than engaging with the question.

**Detection pattern:**
1. Isolate the question's level: factual ("what block controls fingers?") vs methodological ("how do I choose?") vs existential ("what style would I have had?")
2. Check if the answer operates at the same level
3. If not, the answer may be technically correct but unhelpful — flag it

**When YOU are answering:**
- Match the question's level. Philosophical question → engage philosophically. Technical question → give technical answer.
- If you can't answer at the right level, say so: "I can't answer that well, but here's what the data says about X."
- Do not substitute technical advice for existential inquiry just because it's easier to produce.

**The "Socratic mentor" pattern (Jun 2026 user signal, load-bearing):** the user has explicitly said they want a Socratic mentor, not a solution-giver. Verbatim from crody.txt (2025-11-11): *"even though it would be great for u to help me at the same time it means i dident do anything which means i dident make it."* Translated: **doing the work for the user prevents them from learning it themselves, which is the actual point of the conversation.** When the user asks a "how do I..." question:
- **Don't** produce the final answer (the merge recipe, the model pick, the code).
- **Do** surface the perspectives, frameworks, and decision criteria the user needs to make their own call.
- **Do** flag the traps (e.g. "IN00=0.5 will probably break fingers — you want to decide which trade-off is worse for your use case").
- **Don't** pretend the question has one right answer when it has multiple valid approaches. The user has explicitly said there is no right answer in some domains (e.g. aesthetic judgment, model selection).
- **Do** close with a 1-2 line nudge of what to try first, not a prescription.

**The 4 anti-patterns to avoid when the user is learning something:**
1. **Solving it for them** — produces a "right" answer that teaches nothing.
2. **Asking permission to give the answer** — "want me to just tell you the recipe?" defeats the Socratic loop. They asked YOU for help, but help = scaffolding, not the answer.
3. **Hedging so much the user can't act** — "it depends, it's complicated" without a specific next step is not a perspective, it's noise. The user wants perspectives, not paralysis.
4. **Pretending to be uncertain to seem humble** — if you DO know something (e.g. IN00=0.5 breaks fingers 90% of the time), say so. Save the "I'm not sure" for actual uncertainty, not stylistic hedging.

### 7. Source Reputation Verification

**CRITICAL — DO NOT SKIP.** Before presenting search results or extracted content, check the source domain:
- Is the domain a known typosquat (e.g., `shopeemall-dealz.top` vs `shopee.sg`)?
- Is the TLD unusual for the content type (`.top`, `.xyz`, `.click` for a shopping deal)?
- Does the URL structure look suspicious (random substrings, excessive path nesting)?
- Is the site asking for login/credit card info for no reason?
- Is the domain an unknown entity claiming exclusive/too-good-to-be-true info?

If ANY flag fires: discard the result. Note concisely it was excluded for security. Do NOT scrape it.

**Tiered information gathering flow (apply after source verification):**
1. Try standard `web_search` / `web_extract` first
2. If that fails (403, captcha, empty), escalate to browser tools
3. Only use gateway-accessible channels (Discord, Telegram) when standard + browser both fail, OR when the user explicitly asks
4. Document which tier was used so the user understands the source path

### 8. Domain-Specific Knowledge
Keep domain-specific facts in **memory** (e.g., "Morimens is a gacha RPG, currency is Menophin"). The methodology itself lives in this skill. When switching domains (e.g., from Morimens to a new game), the memory doesn't interfere — you research the new domain from scratch using this methodology.

## Pitfalls

- **Echo chambers** — three sources that all quote the same tier list are not three independent sources. Check the citation chain.
- **Recency bias** — a guide from 3 months ago in a live-service game may be completely outdated. Check dates.
- **Survivorship bias** — "this character carried me through endgame" may ignore that the player also has perfect gear/team/dupes.
- **Hype cycles** — new releases are often overrated. Wait 2-4 weeks for the meta to settle before trusting tier lists.
- **Content creator incentives** — "spend your pulls on this banner" content may be driven by engagement, not optimal play.
- **Superficial page analysis** — do not write off a page as "login required" or "no data" without clicking through all UI elements. Expand dropdowns, click filter cards, scroll to the bottom. Many sites show character/weapon lists, filter options, or pricing hints without authentication. The xhxgame.cn Morimens trading page has 58 visible resource filter cards (characters + signature weapons) accessible without login — but you have to click the expand button to see them all. Not exploring = missing data.
- **Wrong tool for the job** — NEVER default to the browser (Chromium) or web search tools for every question. This was a specific, repeated correction: "not every query requires browsing or using the web tool, think about the questions before u want to webscrape, whether its applicable to a general query or questions unless its for research." If the question can be answered from general knowledge, experience, or reasoning — answer it directly. Only reach for web/browser tools when the answer requires factual research, data extraction, or current information you don't have. Examples that do NOT need tools: advice on photo quality, recommending browser extensions, opinion on listing descriptions, general how-to questions.
- **Assuming no credentials exist** — before claiming "I can't push" or "no access," CHECK THE SYSTEM. On Windows with git-bash: check `~/.git-credentials`, `git config --global credential.helper`, Git Credential Manager (GCM), `~/.ssh/`. On Linux/WSL: check `gh auth status`, `~/.git-credentials`. The `github-auth` skill covers the full detection flow. The user has existing credentials — do not claim they don't without checking.
- **Superficial page analysis** — do NOT write off a site as "login required" without thorough exploration. Click every expandable section, scroll to bottom, try unfiltered search, check the JS bundle for API endpoints via `curl + grep 'api/'`, try curl against discovered routes. The xhxgame.cn Morimens site has 58 resource filter cards, a working server select, and search button — all visible without login. I incorrectly wrote it off because I only glanced. Pattern: expand → try → curl → only THEN conclude auth-gated.
- **Arguing with the user** — when the user tells you something works and you think it doesn't, TRY IT FIRST before explaining why you think they're wrong. The user knew xhxgame.cn search works without login. Instead of assuming login was required, I should have attempted the search (select HK, click search) in 30 seconds. This wasted many turns of back-and-forth. Rule: user says it works → try it → only if it fails do you explain why.
- **Narrating the process instead of delivering results** — this is the most frequently violated rule. Do not describe what you're about to do. Do not narrate intermediate steps. Do the work silently, then deliver findings concisely.
- **Over-explaining corrections** — if the user corrects you, acknowledge in one line and fix it. A short "Fixed" or "You're right" is better than a paragraph of self-analysis.
- **Returning scam/unverified results** — presenting search results without checking domain reputation wastes tokens and erodes trust. Before presenting a result, verify the domain is legitimate. If it looks suspicious (typosquat, unknown TLD, too-good-to-be-true), discard it and re-search. Mention the exclusion concisely.
- **Treating a tool's "success" output as truth across systems** — when claiming A → B works (e.g. "Firecrawl calls Ollama"), check the receiving end directly (`nvidia-smi`, `ollama ps`, model load logs). The same discipline applies to the inverse: when a model reportedly loaded but its tag isn't visible, the receiving end is telling you it isn't actually loaded. Don't paper over the discrepancy by trusting the first system.
- **Treating Reddit/vendor blog posts as authoritative** — Reddit threads, blog posts, and YouTube comparisons are leads, not ground truth. Cross-reference with: official docs, code, or your own measurement. For a Reddit claim about config, find the doc/code that confirms the syntax. For a benchmark claim, run your own. Reddit is useful for "what do people actually use" — not for "is this technically true."
- **Subagent output is NOT pre-verified, even when it cites specific numbers (Jun 2026, this user).** When a `delegate_task` research subagent returns "the top r/hermesagent post has 1,019 upvotes," the number came from the subagent's parsing of a Reddit JSON or HTML scrape — not from your own probe. The subagent may have misread the upvote count, parsed the wrong post, or rounded. Real example 2026-06-25: a subagent cited "1,019-upvote Obsidian scaffold" as the #1 r/hermesagent post. The actual top post at the URL had **794 upvotes**. The 1,019 was the subagent's recalled memory of an older version of the same post + a typo. **Rule:** before citing a number from subagent output, verify with a single `web_extract` or `hermes camofox` snapshot of the source URL. If the source disagrees with the subagent's number, use the source's number and tell the user what changed. The cost of verification is one tool call. The cost of citing wrong numbers downstream is losing user trust when they check.
- **Trusting a download that says "success"** — package managers can report success and still fail silently (wrong manifest, partial extraction, missing dependency). Verify the artifact exists and is usable (file size, listing, smoke test). The same applies to model pulls: the CLI may list the model but the API may 404. Always probe the API, not just the CLI.
- **Treating "Real" and "Worth it" as the same question (Jun 2026).** When asked to verify a project ("is X a sham?"), separate two questions: (a) is it real — does the code work, is there real engineering, is the author credible; (b) is it worth the user's time — does it solve a real problem, is the value proposition real vs marketing. Many things are real AND not worth it. The 3-row verdict table (Real? / Useful? / Why) forces both columns. See `multi-source-research-tactics` → "Skepticism-led research pattern" for the full 5-source minimum (Reddit + Google + Gemini + arXiv + GitHub activity) and the README-as-credibility-signal test.
- **Asymmetric marketing-vs-criticism coverage is a yellow flag (Jun 2026).** If a project has lots of Twitter/LinkedIn/Product Hunt buzz but zero critical reviews on Reddit or Hacker News after 2+ weeks, that asymmetry is a signal — the community hasn't engaged yet (early days) OR marketing drowned out skepticism. Surface this explicitly rather than inferring "the absence of complaints = satisfied users." Hit the comments tab on Reddit/YouTube/Product Hunt, not just the link.
- **README "Known Limitations" sections are a credibility signal, not a weakness (Jun 2026).** A real project's README admits limitations ("heuristic detection may misfire," "sync issues during rapid terminal cycling," "untested beta range"). A scam's README claims magic. The presence of an honest limitations section is itself evidence the project is real. Cross-reference: a project that has zero known limitations is either extremely new, extremely small, or hiding something.
- **Anchoring on the first vendor that works** — when a tool partially works (e.g. ollama serves one model but can't load newer ones), the temptation is to wait for the vendor to fix it. Compare first: is the alternative strictly better with no cons? If yes, switch. Don't wait for a buggy incumbent to catch up.

## Verification Checklist

Before presenting a recommendation, verify:
- [ ] Sourced from 2+ independent places
- [ ] Concrete numbers looked up (not assumed)
- [ ] "Best" claim has specific reasoning attached
- [ ] Trade-offs and conditions documented
- [ ] Date of information checked (not stale)
- [ ] Counter-arguments considered

## Token Efficiency: Extraction-First Pipeline

**Key principle (user-taught):** When gathering data from pages, files, or APIs, pre-process with the local model (Ollama Qwen 2.5 7B) before the raw data enters the main model's context.

## Verification Discipline: Avoid False Positives

**This was directly corrected by the user. Read carefully.**

When you claim a tool, model, or pipeline is working, YOUR CLAIM MUST BE VERIFIED WITH INDEPENDENT METRICS — not just the API's `success: true` flag.

### What a `success: true` flag ACTUALLY means

An API returning `{"success":true}` means the HTTP request was well-formed and the server responded without crashing. It does NOT mean:
- The underlying model was loaded into VRAM
- The model actually processed your input
- The returned data came from the model vs a fallback/default path
- The integration between systems (e.g., Firecrawl to Ollama) is wired correctly

**Real example from this session:** Firecrawl's `/v2/scrape` with JSON format returned `success: true`. The claim was "Ollama processed the page and returned structured data." In reality, Ollama's model was never loaded into VRAM (stayed at ~2000 MiB), Firecrawl's LLM extraction was erroring with `model 'gpt-4o-mini' not found`, and the `success: true` was an empty/default JSON object from a fallback code path. The user caught this by checking `nvidia-smi`.

### Mandatory verification checklist for ANY tool/model claim

Before telling the user a system is working:
- [ ] **Model-loaded claim:** Check `nvidia-smi --query-gpu=memory.used` before AND after. A model load shows +4-8 GB VRAM. No change = model didn't load.
- [ ] **Ollama-specific:** Check `curl -s http://localhost:11434/api/ps` — if `models` array is empty, nothing is loaded.
- [ ] **API response body:** Don't just check `success: true`. Parse the response body. Is there actual content? Does it look like it came from the right model?
- [ ] **Process check:** Is the expected process running? `ollama ps`, `docker ps`, `tasklist`
- [ ] **Logs:** Check the service logs for errors. `docker compose -p firecrawl logs api --tail 10`
- [ ] **End-to-end test:** Call the model directly with a known input, verify output is meaningful.

### When you CANNOT verify

If a metric is inaccessible (e.g., can't run `nvidia-smi` on a remote host), say: "I can't verify [X] because [reason]. The API returned [result], but I cannot confirm the model loaded." Do NOT fabricate a verification.

### Rule

> **A `success: true` flag is a hypothesis, not evidence. Verify with a second metric before presenting as fact.**

The user would rather hear "I need to verify that" than "it works" followed by evidence it doesn't.

### Flow
```
Raw data (large, token-expensive)
  → Local Ollama (free GPU) with specific extraction prompt
  → Clean structured JSON (2-5% of original size)
  → Main model context (paid tokens, 96% reduction)
  → Analysis & delivery
```

### When to Apply
- Multi-page listings: batch all pages, send one consolidated extraction prompt to Ollama
- Long documents: extract summaries/structured data locally first
- Repetitive data: define extraction schema once, local model handles volume
- Cost-sensitive: any task costing >$0.01 on main model that can be done locally

### Fallback
If Ollama isn't available (model not loaded, GPU busy): extract via targeted JS in browser (not full page dumps). Use `console.log()` of specific elements, not `document.body.innerText`.