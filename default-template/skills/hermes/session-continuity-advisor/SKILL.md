---
name: session-continuity-advisor
description: "Hermes session lifecycle advisor. Use when (a) the user is starting a new session and asks 'should I start a new session or continue' / 'how should I handle sessions from now on' / 'session discipline' / 'one session per project' / 'where we left off' / 'recall our prior X', (b) context utilization is approaching 80% (the model is forgetting the start of the conversation), (c) the agent notices 50+ unended sessions in state.db during session-open, or (d) the user explicitly asks to plan how to use sessions in the future. Helps the user decide: continue current / reload-context-compact / start-fresh / query-prior-sessions-by-topic. Pairs with the hermes-session-open-inventory skill (which is about the .hermes/ filesystem; this skill is about the session/topic lifecycle)."
version: 1.1.0
author: Hermes Agent + somew
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [sessions, lifecycle, context-window, discipline, mnemosyne, recall]
    category: hermes
    config: []
---

# Session Continuity Advisor

The user's recurring question: *should I /new or keep going? Should I split by topic? How do I avoid the same context getting lost across sessions?*

This skill gives the user (and the agent) a single decision tree for session lifecycle decisions, anchored in hermes' actual mechanics — `state.db`, Mnemosyne cross-session memory, and the context-window utilization of the running model.

## Background — hermes session mechanics

A hermes session has THREE independent storage layers:

| Layer | Scope | Persistence | Searchable via |
|---|---|---|---|
| **Live context window** | Current session only | Lost on `/new` (unless saved) | n/a — model's working memory |
| **`state.db` messages** | All sessions, all time | Permanent (SQLite) | `session_search` |
| **Mnemosyne memory** | All sessions, all time | Permanent (vector + FTS) | `mnemosyne_recall` |

Implications:
- The LLM "forgetting" the start of the conversation is a context-window problem, not a memory problem. Mnemosyne has it. `state.db` has it. Only the in-flight context lost it.
- `/new` does NOT lose history. It just clears the in-flight context. The new session can `session_search` to recover any prior session's content.
- "Reload context" (the compaction button) shrinks the in-flight context by summarizing old turns. The original messages are still in `state.db`; the LLM just stops seeing them in its working memory.

## When to use this skill (trigger conditions)

1. The user asks "should I /new?" / "should I keep going?" / "am I running out of context?" / "where do we usually pick this up?"
2. Context utilization hits ~75-80% — model starts forgetting earlier turns
3. Session-open inventory shows >50 unended sessions (a signal the user has been abandoning sessions)
4. The user mentions "this is a different topic" / "let me start fresh" / "switching projects"
5. The user explicitly wants session discipline rules for the future
6. The user says "state.db is huge" / "session_search is noisy" / "ghost sessions" / "search pulls in old dead sessions" — see the `references/state-db-hygiene-recipes.md` SQLite cleanup recipes

## The decision tree (give the user THIS, not a lecture)

```
Where are you in the current session?
│
├── Topic is DONE (a project finished, a bug fixed, a research arc ended)
│   └─ → /new. Name the new session with a topic tag.
│
├── Topic CONTINUES but context is bloated (75%+ utilization, model is forgetting)
│   └─ → Reload context (in-session compaction). Keeps topic continuity.
│   │
│   └─ If reload doesn't help (compaction too lossy, or this is a long-running thread)
│       └─ → /new. Tell the new session: "Continuing <topic tag>, recall our work via session_search or Mnemosyne."
│
├── Switching to an UNRELATED topic (e.g. coding → cooking)
│   └─ → /new. The new topic doesn't need the old context at all.
│
├── Not sure where the old work is
│   └─ → DON'T /new yet. Run `session_search(query="<topic keyword>")` and `mnemosyne_recall(query="<topic>")` to find prior context. If found, you can either continue OR /new with that prior context loaded.
```

## Naming convention (proposed, user-adaptable)

Hermes session names show up in session_search results and in the desktop GUI sidebar. The discipline:

- **Use kebab-case topic tags**: `ocd-refactor-2026-07`, `db-cleanup`, `sd-prompting-tsukihime`
- **Date suffix if the session will be reopened later**: `topic-2026-07-10`
- **Don't number sequential sessions of the same topic** (`topic-1`, `topic-2`...) — the timestamp already orders them. Use semantic suffixes instead: `topic-setup`, `topic-execution`, `topic-cleanup`.

## State.db hygiene — what the user should know

If `state.db` has 50+ unended sessions, the user has been abandoning sessions. Three consequences:

1. `session_search` lists them all in "recent" — noise on every query.
2. Cross-session recall pulls their content in even when not relevant.
3. Disk grows monotonically; VACUUM reclaims no space because `ended_at IS NULL` rows look "live".

Recommended rule: **end your session explicitly when you finish a topic** (the desktop GUI's "close session" button, or just `/new` with a topic-tagged name). Unended sessions are the hermes equivalent of never closing browser tabs.

**For the actual SQLite cleanup recipes** (orphan-session UPDATE, reasoning-column truncate, VACUUM-while-locked, the FTS5 trigger workaround that silently rolls back UPDATEs): see `references/state-db-hygiene-recipes.md`. Run those recipes when the user says "state.db is huge" or "search results are noisy" — not on speculation. Headline win: Recipe 1 (close orphan sessions) is lossless, takes 30 seconds, and immediately reduces "session_search is noisy" complaints because `ended_at IS NULL` sessions stop showing in recent filters.

## What this skill does NOT do

- Does NOT automatically close sessions (that's a user action).
- Does NOT decide for the user when to `/new` — it gives the decision tree and lets the user choose.
- Does NOT modify `state.db` directly without explicit user go. Use the recipes file when state.db hygiene is requested; the recipes themselves are lossless but each one needs the user to see and approve the predicted delta first.
- Does NOT replace `mnemosyne-recall` or `session_search` — it tells the user when to invoke them.

## Worked examples

### Example 0 — "State.db is huge, search results are noisy"

See `references/state-db-hygiene-recipes.md` for the worked SQLite recipes.
The fastest first move is Recipe 1 (close orphan sessions) — lossless, takes
~30 seconds, immediately reduces "session_search is noisy" because the
`ended_at IS NULL` sessions stop showing in recent filters. Recipe 3
(reasoning truncate) saves ~12 MB but needs the FTS5 trigger workaround
documented in the recipes file. Recipe 4 (VACUUM) needs hermes closed —
defer to a maintenance window.

### Example 1 — "I'm at 50% context, should I /new?"

User: "I'm at 50/162 tokens, do I just /new and rename for discipline from now on?"

Agent response:
- 50% is fine. You have plenty of room. The right time to /new or reload is ~80%+.
- For future discipline: name this session after the topic you just finished (`ocd-refactor-and-db-cleanup-2026-07`), then /new for the next thing.
- Don't /new in the middle of this one — your topic is in flight.

### Example 2 — "Where did we discuss the camofox install?"

User: "What was that thing we did with camofox last week?"

Agent response:
- Don't /new yet. Run `session_search(query="camofox install")` and `mnemosyne_recall(query="camofox")` to find the prior session.
- If found and you want to continue, either stay in current session OR /new with a topic-tagged name (`camofox-install-fix-2026-07-10`) and re-invoke the search.
- If not found in either, the topic genuinely wasn't covered — start fresh.

### Example 3 — "My searches pull in old dead sessions"

User: "session_search keeps showing me sessions from a week ago that aren't relevant."

Agent response:
- This is the "unended sessions" symptom. Run `sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL;"` to confirm.
- If >50 unended, mark them as closed per `references/state-db-hygiene-recipes.md` Recipe 1. Then VACUUM to reclaim space (Recipe 4 — needs hermes closed).
- After cleanup, session_search's "recent" filter will actually mean "recent."

## Agent tic phrases (Class 5 — load this skill when the agent catches itself...)

- "Should I /new?" / "Should I continue?" — user is asking the question this skill answers
- "Where were we?" / "Where did we leave off?" / "Recall our prior X" — user wants prior-session continuity
- "I'm at X% context" / "Am I running out of context?" — context-window pressure signal
- "Start fresh" / "New session" / "Different topic" — explicit session-boundary cue
- "Switching projects" / "Switching topics" — same as above
- "State.db is huge" / "session_search is noisy" / "ghost sessions" — Recipe 1 in references/

## Related skills

- `hermes-session-open-inventory` — what lives where in `~/.hermes/` at session open. Different concern (filesystem audit) but pairs well: this skill decides WHEN to switch sessions, that skill inventories the new one.
- `mnemosyne-memory` — durable cross-session facts. This skill decides when to load it (at session-open if topic is unclear).
- `session` (Hermes Agent built-in) — the broader session-open/close/recall protocol.
- `cross-session-todo-handoff` (v1.0.0, 2026-07-12) — sibling concern, not alternative. This skill decides WHEN to switch sessions; that one decides WHAT carries across. Concretely: when a user is running multiple parallel sessions with different queries, the next session can recover open-work state via `mnemosyne_recall_canonical(category="work", name="in_progress")` (a high-importance dated `mnemosyne_remember` with `valid_until` ~1 month). The discipline: write the handoff at session end OR natural break point, not "at the end of the project" (which never comes). This skill's tic phrases ("where were we", "what's pending", "what did we do last time") should also load that one.

## Pairing with `cross-session-todo-handoff` (NEW 2026-07-12)

These two skills are complementary, not overlapping:

| Question | This skill (advisor) | `cross-session-todo-handoff` |
|---|---|---|
| When should I switch sessions? | Yes (decision tree) | No |
| What open work carries to the next session? | No (only mentions "recall our work") | Yes (canonical `work.in_progress` slot + dated `mnemosyne_remember`) |
| Where do I find prior work? | Yes (`session_search` + `mnemosyne_recall`) | Yes (same, but also reads the canonical slot) |
| When does this trigger? | User asks "where were we?" OR context pressure | Agent reaches a natural break point OR user pivots to a new topic |

**The right pattern when both triggers fire (user says "where were we" mid-context-pressure session):**

1. Load this skill → decision tree → "don't /new yet, run session_search + mnemosyne_recall first"
2. While running the recall, also load `cross-session-todo-handoff` → reads `work.in_progress` canonical slot
3. The two together surface: (a) the actual prior conversation context (via session_search), (b) the in-progress project state (via the canonical slot), (c) the high-importance dated fact (via temporal-weighted recall)
4. Use all three signals to decide: continue, /new-with-tag, or stage-and-restart

**Tic phrase that should fire BOTH skills together:** "Where were we?" / "What's pending?" / "What did we do last time?" — the advisor answers the *where*, the handoff answers the *what's still open*. Load both at once; they take 5 seconds combined.

**Anti-pattern:** only loading the advisor. The advisor says "recall prior work" but doesn't tell you HOW to record what you discovered in a form that survives the next session. Conversely, only loading the handoff without the advisor: you'll write a handoff but not know whether the user wants to /new or continue. Always both, when the user's question touches session boundaries + project state.

## References

- `references/state-db-hygiene-recipes.md` — SQLite cleanup recipes for state.db
  (orphan-session close, empty-session delete, reasoning-column truncate with
  FTS5 trigger workaround, VACUUM-while-locked diagnostic). Use when the user
  asks for state.db maintenance or complains about session_search noise.

## Changelog

- **v1.1.0 (2026-07-10):** Added `references/state-db-hygiene-recipes.md` capturing the FTS5 trigger workaround, orphan-session UPDATE, and VACUUM-while-locked problem from the 2026-07-10 OCD refactor session. These are session-lifecycle concerns that belong with this skill rather than as a standalone umbrella. Bumped worked-example #0 to point at the recipes file. Added tic-phrase row for state.db hygiene complaints.
- **v1.0.0 (2026-07-10):** Initial extraction from the 2026-07-10 OCD-refactor session where the user asked "should i just start one new session and rename and start from there from now on as discipline?" Source: `~/.hermes/skills/hermes/hermes-skill-loading-disciplines` Pattern 5 (agent self-tic) + Pattern 11 (version-skew + staging) informed the decision-tree shape; the mechanics section derives from live state.db inspection (415 sessions, 100 unended, 11.4 MB reasoning columns truncated).