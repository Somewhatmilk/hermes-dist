---
name: deep-research-methodology
description: "5-layer framework (breadth / depth / time / cross-validation / meta) for expanding research beyond surface-level. Use when the user says 'go deeper' / 'research more' / 'expand' or when initial research returned too few actionable answers. Triggers: 'research X more', 'go deeper', 'expand on this', 'I need more sources', 'I haven't found what I need'. Skip when: the user has already given concrete sources/URLs/IDs, when the topic is well-bounded, or when an inline lookup is sufficient. This is the v0.4.8 trimmed universal cut (~15 KB) — original 38 KB operator-specific sections (Morimens case, a11y virtualization, aesthetic recs) removed."
version: 1.1.0
author: Hermes Agent (default profile, derived from multi-session research sweeps 2026-04 through 2026-07)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [research, methodology, breadth, depth, cross-validation, sources, sweep]
    category: research
    related_skills: [information-validation, multi-source-research-tactics, web-research-stack, research-refresh-ritual, deep-research-methodology]
    config: []
---

# deep research methodology (5 layers)

when the user says "go deeper" / "research more" / "expand" or when initial research returned too few actionable answers, the failure mode is usually surface-level coverage. this skill is the 5-layer framework to break out of that.

**core principle: re-search from orthogonal angles. don't just open more tabs on the same query.** if layer 1 found 5 reddit threads and that's not enough, layer 2 is NOT "open 5 more reddit threads" — it's "now read the full content of the 5 you have, then layer 3 is old/newer, then layer 4 is cross-source."

## layer 1: breadth — more sources

**vertical: more platforms for the SAME topic**
- reddit: try multiple subs (r/X, r/Y, r/Z) — game subs often have a "main" + adjacent subs (r/GachaGameRecs, r/GameDeals, r/visualnovel)
- discord: not just the server the user is in, but adjacent servers (r/Morimens + related gacha communities)
- off-platform: steam community discussions, fandom wiki, namu wiki (KR), gamewikis, gamerch
- 4chan / greentext / archived boards: weak signal, but unique on niche topics

**horizontal: more posts within the same platform**
- top-of-all-time, top-of-year, top-of-month (recency matters for some topics, ancient for others)
- controversy / hot threads (high comment count = more debate, more perspectives)
- the "consensus top post" + the "controversial counter-post" pair (you'll learn more from the disagreement than from either alone)

**the "main" + "adjacent" pattern**: when a topic has 1 dominant community, the adjacent communities often have orthogonal opinions. e.g. r/Morimens is the main gacha game sub; r/GachaGameRecs is the cross-game comparison; r/visualnovel is the format-overlap.

## layer 2: depth — read full content

**don't skim**. open the post, read the full text, read the top 5 comments, then read the OP comments. the title is a hook; the body is where the actual claim lives; the comments are where the community validates or refutes.

**extract the post's evidence chain**: what sources did the OP cite? what data did they link? what was their testing methodology? the "go deeper" usually means "go from title-claim to evidence-claim."

**if the post is a question post**, read the top answer + the top dissenting answer. the "accepted answer" can be wrong; the disagreement is the data.

**if the post is a discussion post**, read the OP carefully, then read the top 5 comments sorted by score, then the top 3 controversial (low-score-but-replied-to) comments.

## layer 3: time — older + newer

**two passes on time**:
- **older**: search 2023-2024 if your topic has historical context. some categories (anime, gacha, retro hardware) have rich 2018-2022 archives that newer posts reference.
- **newer**: search the past 90 days specifically. Reddit/HN search defaults to "all time" which buries the recent posts. filter by date aggressively.

**if the topic is volatile (model releases, CVE advisories, game patches)**: recency dominates. skip the historical layer entirely, focus on the past 14 days.

**if the topic is durable (philosophy, design principles, tool comparisons)**: 2023-2024 is the sweet spot for high-quality long-form posts that newer short-form posts reference.

## layer 4: cross-validation

**a claim is not "validated" because 5 reddit posts repeat it.** it is validated when:
- at least 2 independent sources make the same claim with different evidence chains
- the claims are testable (you can run a query, read a doc, verify a code path)
- the disagreeing sources are addressed (not dismissed — addressed)

**the "5 sources" trap**: 5 reddit posts repeating the same wrong info is 1 source of evidence, not 5. cross-validation requires INDEPENDENT evidence chains.

**for technical claims (tool comparisons, library versions, API behavior)**: the OFFICIAL docs / official repo is the canonical source. reddit/HN discussions are evidence that "users have this experience" but NOT evidence that the claim itself is true. cross-check against the source.

**for community claims ("most users prefer X")**: reddit/HN are the canonical source. don't try to find an "objective" source — there isn't one.

**for stats claims ("X% of users do Y")**: distrust ALL single sources. even official survey results. if 2 independent surveys say the same thing, that's evidence. if only 1 survey says it, that's a hypothesis, not a fact.

## layer 5: meta — track what worked

**after each research pass, log**:
- what query strings worked
- what sources were productive
- what sources were dead ends
- what the time-to-answer was
- what the user accepted vs. pushed back on

**the meta layer is what makes future research faster.** without it, you re-derive the same search queries every time. with it, your "I remember reddit/r/X had a great thread on this 2 weeks ago" recall improves.

**where to log**: scratchpad (in-session) + a per-topic research journal file at `~/.hermes/research/<topic-slug>.md` (durable, cross-session). the journal is the durable artifact; the scratchpad is the short-term.

---

## pitfall: respect the provider call budget — parallel web batches kill small custom providers (NEW 2026-06-27, this user)

if you're using a custom provider (e.g. MiniMax-M3 with a 1500-req/5h budget), parallel `web_extract` / `web_search` / `camofox` calls in one assistant turn can burn your budget in 10 minutes. **batches of 4-6 parallel calls max**, not 10+.

**symptom**: budget exhausted mid-research, getting 429s on every subsequent call, can't finish the layer 4 cross-validation.

**mitigation**:
- count your budget at session start: 1500 req / 5h. if 800 already used, you have 700 left.
- batch web calls in groups of 4-6, with sequential calls between batches.
- save the cross-validation (layer 4) for AFTER the initial breadth+depth pass. you might find the cross-validation isn't needed.
- if budget is tight, **stop at layer 3** and tell the user the cross-validation is partial. better than 429ing out.

## pitfall: user says "scrap all N pages" / "research X more" — ask for 1 sample URL first

if the user says "research X more" without specifying sources, the safe first move is to ask for **1 sample URL of what they're looking for**, not to launch a broad sweep.

**why**: the failure mode is burning 50+ web_extract calls on a misread of what the user wanted. e.g. user says "research the gacha model" and you go deep on Morimens gacha, but they actually meant gacha analytics SaaS. 50 calls, all wrong.

**the right flow**:
1. user: "research X more"
2. you: "before I sweep — is there 1 URL or post I can read to anchor what you mean? e.g. an example of the type of answer you're hoping for"
3. user provides 1 URL
4. you: read that URL, extract the **structural** features (what kind of post, what evidence chain, what tone), then sweep for MORE posts with the same structure
5. sweep, cross-validate, present

**cost**: 1 clarifying question. saves 50+ wrong-direction calls. always ask.

## pitfall: AUDIT IS NOT RESEARCH — the local-disk trap (NEW 2026-07-05, this user)

if the user says "research X", do NOT start by reading local files in `~/.hermes/` or `~/Documents/` thinking "maybe the user already has notes on this." that's an audit, not research. the user wants NEW information, not a re-read of their own files.

**the local-disk trap**:
- you find a note from 3 months ago on the topic
- you summarize the note
- you present the summary as "here's what I found"
- the user wanted fresh research, not their own prior notes summarized back to them

**the right move**:
1. if the user explicitly says "check my notes" or "look at what I have on this" → audit mode, read local files
2. if the user just says "research X" → sweep the web, do NOT start with local files
3. if you DO have a relevant local file from prior work, **mention it** ("I have notes from YYYY-MM-DD on this, want me to re-research fresh or build on the prior notes?") — let the user choose, don't decide for them

## pitfall: chasing inline links in tool-recommendation threads (NEW 2026-07-03, this user)

in tool/library recommendation threads, the OP and commenters cite tools by name with links. **following every link to read the linked article is a rabbit hole** — 90% of the time the link is to a low-quality blog post or a marketing page, and the actual signal is in the comment thread ABOUT the link.

**the right move**:
1. read the OP, extract the tool list
2. read the top 5 comments, extract the recommendation consensus
3. STOP. do not follow the links.
4. the wiki-curated list (per the next pitfall) is where you go for actual tool details.

**cost saved**: 10-20 web_extract calls per recommendation thread. those calls are way more useful spent on layer 4 cross-validation than on reading marketing pages.

## pitfall: probe MCP endpoint liveness before assuming the MCP tool works (NEW 2026-07-12, this user)

if you're planning to use an MCP tool (e.g. `firecrawl_endpoints_v2`, `camofox`, `web_extract` via a custom provider), **probe the endpoint first** before committing to a research strategy.

**the failure mode**: you plan a research sweep assuming `web_extract` works. you call it. it returns empty / 500 / auth error. now your research strategy is broken and you've burned 20 minutes of context.

**the probe** (1 call, 2 seconds):
```
curl -s -o /dev/null -w "%{http_code}" https://your-endpoint/health
# or for MCP tools, just call them with a trivial input first
```

**if 200**: proceed. if 401: re-auth. if 503 / connection refused: ABORT and tell the user the MCP is down. do NOT proceed with a broken tool — you'll waste the rest of the session.

**the "do not call a research tool that hasn't been probed" rule** is a meta-rule for ALL layer 1 work, not just MCP. if you're going to use a tool, call it once with a trivial input first. 1 cheap call vs. 50 expensive calls in a broken strategy.

## pitfall: don't over-interpret feedback (learned 2026-06-22)

if the user pushes back on a research output, **read the pushback literally before re-interpreting it**. the failure mode is over-correcting: user says "you didn't cover X" and you go re-do the entire research, when the user actually wanted you to JUST add X to the existing output.

**the right move**:
1. read the user's pushback
2. if it's a specific missing item, add THAT item to the existing output
3. if it's a structural complaint (too shallow, wrong angle), re-do the research with the structural fix
4. if unclear, ask. 1 clarifying question > 30 minutes of misdirected re-work

## pitfall: ALWAYS check the OFFICIAL community + official repo's curated showcase FIRST (captured 2026-06-24)

if the topic is a tool / library / model / platform with an official community, **the official community's curated list is the canonical source**. do NOT start with reddit.

**the right order**:
1. official repo's README + /docs/ + curated showcase (1-2 calls)
2. official community's wiki/Discord pinned resources (1-2 calls)
3. **then** reddit/HN for community sentiment, edge cases, workarounds
4. **then** personal blogs / YouTube for tutorials

**the failure mode**: starting with reddit for a "what's the best X" question. reddit discussions are noisy, often 5 years stale, and the top-voted answer is often the most generic not the best. the official community's curated list is curated FOR this purpose.

**examples** (operator-specific, removed from v0.4.8 trimmed version):
- for SD models: civitai's curated list + the model's official HF page
- for gacha games: the official subreddit's wiki + the game's Discord pinned resources
- for hermes: the official `~/.hermes/skills/` library

## pitfall: delegated fan-out research needs artifact-first verification (NEW 2026-07-02)

if you delegate research to a subagent (leaf-agent or kanban-worker), **the first thing you do on receiving the subagent's output is verify the artifacts, not the narrative**. the subagent's summary is a CLAIM, not EVIDENCE. the evidence is the artifacts it produced (URLs fetched, post IDs found, file paths created).

**the right flow**:
1. subagent returns: "I found 5 sources on X, here's the summary"
2. you: "show me the 5 URLs / post IDs / file paths"
3. you: independently verify each (1 quick `curl` or `web_extract` per URL, or `ls` of the file)
4. THEN you present the summary to the user, with the verified artifacts as evidence

**if the subagent's summary doesn't match the artifacts**: the subagent hallucinated. don't present the summary. send it back with "your claim X doesn't match artifact Y, re-check."

**the cost of skipping this**: you present a hallucinated summary as research. the user trusts you. the user acts on it. the user gets burned. this is exactly the failure mode the consolidation-stripping pattern is meant to surface, and you can't fix it after the fact if you don't verify the artifacts upfront.

## pitfall: don't trust the GitHub README — check the official docs site for the curated list

the GitHub README is the **first-impression** view of a project. the **canonical, curated view** is the docs site or the official wiki. the README has cherry-picked examples, the docs site has the comprehensive list.

**the right move**:
1. README for "what is this project, who's behind it, install steps"
2. docs site / wiki for "complete API surface, all options, curated examples"
3. issues / discussions for "known bugs, workarounds, current state"

**the failure mode**: relying on the README for the API surface. you miss options that the docs site has. you use deprecated flags that the docs site explicitly removed. you spend 30 minutes debugging what the docs site would have told you in 30 seconds.