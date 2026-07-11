# Agent Self-Tics → Skill-Load Triggers

The list behind Class 5 ("Agent self-tic trigger") of `SKILL.md`. The discipline: when the agent catches itself about to write one of these phrases during drafting, it calls `skill_view(name)` for the matching skill BEFORE the response leaves. This is a self-discipline, not a runtime hook — Hermes' loader does substring match at session-start index time and cannot inspect in-flight draft text.

## Verified tic inventory (2026-07-05 seed)

| Tic (case-insensitive) | Moment | Skill to load |
|---|---|---|
| "holy shit" / "oh wow" / "huge find" / "massive findings" / "big find" / "major red flag" | About to research deeply; structural implication | `subagent-decision-matrix` |
| "let me pre-flight" / "first dispatcher profile" / "before I delegate" / "before I dispatch" / "I should call" | About to dispatch a subagent | `session` + `hermes-profile-dispatch-rules` |
| "mystery solved" / "root cause was" / "now I see it" / "I see the bug" / "off by one" / "found it" | Just found a real bug after confusion | `hermes-misbehavior-diagnosis` (then write up cleanly for the user) |
| "direct answer first" / "honest answer to your question" / "reconstruct" / "no, actually" / "actually..." | Under pressure to be candid, or just admitted something | `prompt-interview-pattern` (continue the direct style) |
| "I should have caught this" / "you're right" / "fair point" / "Mystery solved" | User caught a failure | `failures-journal` (log + commit to memory) |
| "let me try a different approach" / "different angle" / "pivot" / "new plan" | Pivoting after 2+ failed attempts | `systematic-debugging` (formal pivot) |
| "this is a mess" / "I made it worse" / "now it's broken" / "rolled something back" | Caused regression | `failures-journal` (log) + `hermes-misbehavior-diagnosis` (fix) |
| "I'll just use web_search" / "let me search" / "quick search" / "let me google" | About to invoke a single search tool as the **first** search-class action | STOP — recall the search-research canon (`mnemosyne_recall(query="search research canon tinysearch web_search order")`). Default if missing: `tinysearch_research` → `tinysearch_scrape_url` / `web_extract` on top 2–3 URLs → `web_search` only as last-resort fallback. See SKILL.md Pattern 9b. |
| "based on what I know..." / "from my experience..." / "it's well-known that..." / "widely known" | About to assert from recall or pattern-match without citation | STOP — issue `mnemosyne_recall` for the search-research canon, then run the search through the canonical ordering before claiming. See SKILL.md Pattern 9b. |
| User turn contains: "is this evidence-backed" / "back it up" / "actual research" / "from sources" / "don't make it up" / "verify" / "research like I said" | User-side tic signaling multi-source canon required | STOP — recall the canon, restart the search through `tinysearch_research` → scrape top 2–3 URLs → only then assert with citations. See SKILL.md Pattern 9b. |

## The discipline — concrete steps

When you catch yourself about to type a tic phrase (in any turn, any context):

1. **STOP the draft.** Don't finish the sentence.
2. **`skill_view(name)`** for the matching skill from the table. Wait for it to load.
3. **Re-read** what the skill's body / first reference says about how to handle this moment.
4. **Continue the draft** following the skill's guidance, not the off-the-cuff response.

Failure mode if you skip this: the agent writes the trivia / commentary / plan ABOUT the skill instead of USING the skill. The user sees a recipe they implicitly asked you to apply.

## Mining for your own tics

The table above is seed data from one user's session history (and one agent's verbal habits). To grow it:

1. **After each session**, scan your own transcripts for phrases you said at notable moments (just before a discovery, a bug found, a failure acknowledged, a dispatch made, a pivot).
2. **For each tic discovered**, add a row with: the phrase, the moment it signaled, and which skill would have helped.
3. **Periodically prune** tics that turned out to be noise (rare or non-actionable).

The discipline compounds — every session that uses the table sharpens the next session's self-recognition.

## The "dead skill" mutation rule

Sometimes the tic signals a skill that **exists but never fires**. `failures-journal` is the canonical example — documented in Mnemosyne memory as the agent runs the failing operation 3 times before manually logging, because its description is "Capture failures when they happen" — useless as a trigger.

When you discover a skill that exists but never fires:

1. **Patch its description** to the trigger-rich pattern (Class 2 — keyword-implied triggers with explicit "Use when (a)... (b)... Trigger phrases: 'X', 'Y', 'Z'").
2. **Add a tic mapping** here so the moment-of-failure tic forces the load.
3. **Verify the next session** actually fires the skill without manual intervention.

If a skill genuinely has no useful triggers and no useful tics, **delete it** rather than letting it collect dust. The hermes-curator cron handles this at scale; you can prompt-delete a single skill with `skill_manage(action="delete", absorbed_into="")` if you find one mid-session.

## Why this matters (the meta-lesson from 2026-07-05)

The user explicitly taught: *"u know what trigger phrases should also triggers based on your own words that u repetitive use for certain areas. Example when u think u found gold u say holy shit"*.

That comment was the missing pattern. The agent had descriptions that fired on user phrases, but no discipline for catching its own phrasing patterns. The skill ecosystem stopped at Class 2 (keyword-implied triggers); we never thought to model the **agent's own** verbal habits as inputs.

This reference is the implementation. Add tics as you discover them. The discipline compounds.
