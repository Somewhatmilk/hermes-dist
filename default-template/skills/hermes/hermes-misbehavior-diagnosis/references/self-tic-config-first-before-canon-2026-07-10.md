# Self-tic: check the actual tool default before falling back to a canon / heuristic / agent-defined pattern (NEW 2026-07-10)

**Trigger:** any time the agent is about to use a default it remembers from training or a previous session, or to "fall back" to a known-good pattern — pause and check whether the runtime exposes an explicit tool/flag/parameter that supersedes the canon.

**What you do:**

- For tool/CLI defaults: run `hermes config show` (or `hermes <tool> --help`) **FIRST**. If a config key already exists for the parameter, set it. If no key exists, **flag the gap — don't invent one**. Canon is the fallback, not the first resort.
- For web/research routing: tinysearch → tinysearch scrape_url → web_extract → web_search → Reddit/camofox. **Before falling back, check whether the user's `hermes config` exposes a `web_search` or research tool that supersedes the canonical order.** Per the user, the canon was true at the time of writing; it may have been superseded by config that the agent hasn't loaded yet.
- For Mnemosyne / Cron / Kanban: the same. `hermes config list` and `hermes config show` are the equivalent of "check the current X first" for configuration.
- For any "I'll just use the default I remember" decision: **the canon is a fallback, not a starting point. Check the live config first, run the live diagnostic, then fall back to canon only if no config / diagnostic exists.**

**User verbatim (2026-07-10):**
> *"--- 1 Before falling back to canonical search routing, check hermes config list and hermes config show for an existing tool default. If a key exists, set it. If no key exists, flag the gap — don't invent one. Canon is the fallback, not the first resort."*

**Failure mode this prevents:** in the same 2026-07-10 turn, the agent defaulted to `web_search` for a research query when the user had `tinysearch_research` configured as the primary — the agent skipped over the live config and used the canon from training instead. Result: extra round-trip (the user had to push back), unnecessary API cost, and a complaint that the agent "defaulted without checking the current X first."

**The opposite failure mode (covered separately):** "Predicting-a-cause-without-running-the-diagnostic" (v2.7.0) is about claiming a fix will work without running the test. This self-tic is upstream of that one — it covers the *decision* of which path to take (config-first vs canon-first), not the *verification* of the result.

**Cross-reference:** this is structurally similar to the "check the current X first" trigger phrase already in the SKILL.md frontmatter (v2.4.0 added `check the current X first`, `is that what we expect or is it actually a bug`). This entry extends that pattern to the agent's own choice of default — not just the agent's reading of state, but the agent's choice of WHICH canon to apply.
