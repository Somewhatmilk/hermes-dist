## The "should this be a NEW profile?" decision tree (added 2026-06-26, this user)

The bigger-field rule above says "don't create a new profile when the work fits an existing field." That tells you when **not** to create. It doesn't tell you the full decision. The full decision has 4 questions, in order:

| # | Question | YES → | NO → |
|---|----------|------|------|
| 1 | **Is this a recurring long-term field of study** (with its own canon of skills, vocabulary, sources) — or a one-time audit / meta-task / single project? | Continue | **Use `default`.** One-time work doesn't need its own profile. |
| 2 | **Does an existing profile's parent field already cover this** (do the vocabulary, sources, and deliverables overlap)? | **Use the existing profile.** | Continue |
| 3 | **Is this work distinct** from every existing profile's field — different vocabulary, different sources, different deliverables (not just different topics within the same field)? | Continue | **Merge into the closest existing profile** (or add skills to `default`). |
| 4 | **Will this work need persistent memory, persistent kanban state, or a skill inventory of its own?** | **Create new profile.** | **Use `default`** — the work fits under existing profiles OR is one-time/short-term. |

**Examples that resolve to "use default":**

- *"Review all the profiles and current skills, tools, MCPs, agents — are they working together harmoniously?"* → meta-task, one-time audit. **default.**
- *"Summarize today's session"* → one-time meta-task. **default.**
- *"Diagnose why this script is failing"* → debug session. **default** (or `software-engineering` if it touches devops/cron/plugins).
- *"List the files in this repo"* → read-only inspection. **default.**

**Examples that resolve to "use existing profile":**

- *"Audit my WordPress site's SEO"* → `communicate-design` (web + SEO + content, all within its field).
- *"Optimize my Airbnb listing for KL market"* → `communicate-design` (STR is a child process of communication-design per bigger-field rule).
- *"Build me a CLI to do X"* → `software-engineering` (the field of software engineering).
- *"Review my system prompt"* → `prompt-engineering` (the field of prompt engineering).

**Examples that would resolve to "create new profile"** (rare, requires strong evidence):

- A user takes on a recurring long-term engagement in a field that genuinely doesn't overlap with any existing field's vocabulary/sources/deliverables. Example: a user becomes a working illustrator and starts freelancing. There's no existing `creative-design` profile. Illustration is its own canon (color theory, composition, brushes, anatomy). Create `illustration-design`.

**Anti-pattern that fires this rule:** when the user says "create a new profile for X," the agent often just creates it. **Don't.** Run the 4 questions first. Most "I need a profile for X" requests resolve to "fit X into existing profile" (Q2 or Q3 = YES). The bigger-field rule is the load-bearing reason: splitting work into narrower profiles makes the agent context-switch more, not less.

**The "scope creep" cousin:** creating a profile via `cp -r profiles/X profiles/Y` is also covered by this decision tree (Q3: the new profile is just a copy, so it's not distinct from X — answer is "merge into X" or "regenerate SOUL.md from scratch"). See the "Profile clone trap" section below.

**Cross-reference:** the bigger-field rule (above) is the underlying principle. This decision tree is the operational version.
