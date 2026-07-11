# Structural-change pre-check (NEW 2026-06-28, user-pushback signal)

The inventory is not just for "is X installed" questions. **Before proposing ANY structural change to the user's Hermes install** — new profile, new board, new skill, new "planner" persona, new dispatch mode — run the full live inventory first:

- `hermes profile list` (the profile directory is on disk; that is truth)
- `hermes kanban boards list` (active board registry)
- `hermes config show | grep -A30 ^auxiliary` (the auxiliary-role config — the user's "planner" lives here as `auxiliary.triage_specifier` + `auxiliary.kanban_decomposer`, NOT as a separate profile)
- `ls "$HERMES_HOME/skills/"` and `ls "$HERMES_HOME/profiles/"` (what skills and profiles are already on disk)
- `hermes kanban list --json` on the target board (so you don't create a sibling ticket that already exists as a child of a parent)

## Live case 2026-06-28

The agent recalled "user has no profiles, no swarm, no planner" from a stale earlier session and proposed creating all of it. Live state showed: 7 profiles already exist, swarm pattern already wired, "the planner" is two auxiliary roles in config.yaml. The user pushed back: *"have u analyze our own workflow and compared?"* Lesson: a "let me add X" proposal that touches the user's own install must be preceded by the live cross-check. Memory is a cache, not the source of truth.

**Trap pattern:** the inventory verification is treated as optional for "small" structural changes ("just adding one profile"); it isn't. One missing check is enough to propose building something that already exists.

## The "review your prior recommendation honestly" pattern (companion)

When the user challenges a community-pattern recommendation with "but we already have X, is this necessary?", the right response is **not** to defend the recommendation or pivot to "but hear me out." It is to re-examine the recommendation against **what the user already has on disk right now** (after the inventory above). The honest answer in the 2026-06-28 case was:

- Skip A (5-role profile pattern) entirely — the user already has the roles, just named differently (`auxiliary.triage_specifier`, `auxiliary.kanban_decomposer`, etc.). Recommending the canonical pattern would be **redundant work for cosmetic naming**.
- Defer B (self-improving skills) by 2-4 weeks — the infrastructure is there (curator, evolve_skill, Mnemosyne) but model quality is the bottleneck.
- Real recommendation: patch the dispatcher to use `delegate_task`. That single change compounds across everything else.

The user engaged substantively and pivoted to the dispatcher fix instead. The "here's why my prior recommendation was weaker than I made it sound" framing was valued, not punished.

**Rule:** before recommending a community pattern, ask:

1. Does the user have the capability already, even if named differently?
2. Does the pattern require a different infra the user lacks?
3. Is the cost (new profiles, new skill, new concept) actually worth the benefit (clarity, consistency), or is it just naming?

If 1 is "yes" and 3 is "no" — skip the recommendation. The user will tell you if they actually want the rename.

**Trap pattern:** the agent defends a recommendation by rephrasing it, listing 5 community quotes, or pivoting to "well, technically..." — none of which address the user's actual question, which is "is this work I need to do?"