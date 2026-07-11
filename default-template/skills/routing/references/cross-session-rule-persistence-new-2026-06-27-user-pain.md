## Cross-session rule persistence (NEW 2026-06-27, user pain)

User explicit feedback: "everytime i start a new session u either forget the rules placed by the last session or dont follow them. how can we combat this."

This is the load-bearing issue behind the persona layer, SOUL.md, Mnemosyne, and skill library. The mechanism stack:

| Layer | Survives session restart? | Survives rule update mid-session? | Cost |
|---|---|---|---|
| **SOUL.md** | ✅ (read from disk) | ❌ (mutating busts cache) | ~3K tokens, cache-stable |
| **Mnemosyne canonical memory** | ✅ (SQLite DB) | ✅ (version chains) | auto-injected, recall-on-demand |
| **Mnemosyne v3.10 persona layer** | ✅ (memoria_persona table + persona.md) | ✅ | auto-injected, separate from SOUL.md |
| **Skills (SKILL.md)** | ✅ (file write) | ✅ (separate cache slot) | loaded on demand |
| **config.yaml always_load** | ✅ (read from disk) | ❌ (restart needed) | always in context |

**3 separate places to put user-specific facts to make them persist:**
1. **SOUL.md** = agent identity, behavior rules, voice, boundaries. What the agent IS. Cache-stable, byte-identical for the conversation's life.
2. **Mnemosyne persona layer** = user-characterization (their style, preferences, stack, frequent corrections). NOT agent identity. Auto-injected per session, NOT cache-stable.
3. **Mnemosyne canonical memory** = recalled on demand, NOT auto-loaded. For specific facts that aren't always needed but should be retrievable.

**Don't duplicate the same fact across all three** — that wastes tokens and creates drift when one is updated but not the others. The 2026-06-27 diagnostic work showed this concretely: a candidate persona design for SOUL.md mixed user-characteristics (lowercase register, 6-profile structure) with agent-identity (behavior rules, boundaries). The split is: agent-identity → SOUL.md, user-characterization → persona.md, session-specific state → Mnemosyne canonical.

**The "rules get violated" failure mode the user described** is NOT a recall problem (memory recall is not the bottleneck). It's one of:
- **Goal-vs-rule attention war** — the user's current goal-shaped message gets more attention than the abstract procedural rules in SOUL.md
- **Stale info as authoritative** — Mnemosyne recall ranks by `vec + FTS + importance` (0.5/0.3/0.2), and high-importance older memories outrank low-importance newer ones
- **Tool budget pressure** — by tool call 8-12, the context is full of tool results, the original system prompt is at the start, model attention is recency-weighted, rules fade
- **Abstract rules vs concrete goals** — procedural rules need to be inlined into the goal structure ("to accomplish X, you must NOT do Y") not sitting as sidecar

Diagnostic is the first step. Fix cannot be prescribed without data. Build a rule-violation audit tool that scans recent session transcripts and reports which rules were violated, in which turn, and what tool call preceded the violation. Without the data, architectural changes (polyphonic recall, daemon, persona layer) are guesses.
