## When dispatch facts come from memory — verify against live state, not recall (NEW 2026-06-27, this user, fresh-session failure)

The default profile's dispatch decisions (which profile owns joandrew, which board to write to, which CLI flags are current) all come from Mnemosyne recall. Recall is **ranking, not truth** — it returns the most-similar memories, which may be older-but-similar copies of facts that have since been superseded.

**The specific failure (this session):** a recall for "joandrew owner profile" returned TWO memories, both `importance: 0.95`:
- 2026-06-24 13:40: "web-designer (NEW, created 2026-06-24) = joandrew.com.sg manager"
- 2026-06-24 14:02: "communicate-design now owns joandrew; web-designer was deleted"

I picked the first one because of higher vector similarity, even though the second explicitly supersedes it. Result: a sentence in my explanation said `web-designer` when the actual answer was `communicate-design`. (The ticket itself was correctly assigned — only the narration was wrong, which is the worst kind of wrong because the user can't catch it from the artifact.)

**The rule (encodes how the recall engine actually ranks):**

1. **Same-importance ties → recency wins, not vector similarity.** Mnemosyne scores by `vec + FTS + importance` (0.5/0.3/0.2 weighted). When two memories have equal importance, the more-recent one is the truth unless the older one is the *source* the newer one is updating. If a newer memory's content explicitly says "X is the new Y, superseding Z" — that newer memory wins, period. Don't weight it by vec similarity to the query.
2. **Verify dispatch facts against live CLI, not memory.** Before writing a kanban ticket, run `hermes profile list` and `hermes kanban boards list`. The recall may have a stale profile or board name; the CLI has the ground truth. Cost: 1 tool call, 2 seconds. Stops entire classes of "I sent work to a deleted profile" failure.
3. **Memory_id mutations require content verification.** Before any `mnemosyne_invalidate` / `mnemosyne_forget` / `mnemosyne_update`, the recall returns a `content_preview` — that preview IS the verification handle. The ID is opaque; the content is what you're actually mutating. If the preview doesn't match what you think you're mutating, **stop and re-recall with a more specific query**. Real failure this session: I tried to invalidate a stale memory, picked the wrong ID (the one above the stale one in recall order), and silently killed an unrelated dispatch-gotcha memory. Recovered by `mnemosyne_remember`-ing the killed content back, then invalidating the right ID.

**Cross-reference:** the underlying rules (same-importance-recency, invalidate-vs-forget) live in `mnemosyne-memory` (Pitfalls section). The reason they're ALSO here: this skill's reader is the default profile, and the default profile is the one that does dispatch — so the operational manifestation belongs in the dispatch skill, with a pointer to the memory-side source of truth.
