# True-forget rule: orphan paths and verified-absent facts (2026-07-09, this user)

**User-preference signal (verbatim, 2026-07-09):**

> "yep but i want u to note this is the fourth time in multiple sessio nu
> layed out that AppData/Local/hermes is orphaned meaning u truly never
> deleted it, if u want to forget it just dont even try to memorize it
> after deleting it that its orphaned to truly forget it"

**The pattern that produced this:** across 4 sessions, prior agents kept
re-memorizing "AppData/Local/hermes is orphaned" — each new memory note
re-encoded the orphan as a fact, defeating the point of removing it.
The user noticed the pattern, pushed back, and gave the durable
directive: **true forget = invalidate, no replacement.**

This is a class-level rule for how to handle verified-absent facts in
Mnemosyne. It applies to every profile, not just one project.

## The rule

When a multi-path scan + CLI verification confirms a path is absent:

1. **`mnemosyne_invalidate` any existing memory that encodes the
   absence** (or the path itself). No replacement.
2. **Write NO positive "X is absent" memory** in its place. The orphan
   should be invisible, not a recurring confirmation the agent has to
   re-process.
3. **Update hybrid cases** (rule is still valid, only the path
   reference is stale) with a positive restatement that drops the
   absent-path reference.
4. **Verify nothing in SOUL.md / config / skills still references the
   path** before considering the forget complete.

## When it IS appropriate to memorize an absence

Negative facts are real (a path really is absent right now), but they
age faster than positive facts and have a high re-encoding cost. The
user's tolerance for "wrong positive fact" is much higher than for
"noise memory that keeps confirming the same negative." Three cases
where memorizing an absence IS appropriate:

(a) **The path is load-bearing for future operations** — a config key
the user might mis-type. Memorize the right positive value once, not
"X is absent."

(b) **The absence was caused by a destructive action in THIS session**
and the user needs a "I just deleted X, here's where it went" trail.
Use the failures journal or a session-private note, NOT Mnemosyne.

(c) **The absence IS the user's expressed preference** — "I never use
X." Write a short positive note ("X is unused"), not a negative
orphan-confirmation.

For all three, write a short positive note. The shape is "X is Y" or
"I deleted X on DATE, archived to PATH", not "X is absent" or "X is
orphaned."

## Why this is a routing-level rule (not project-level)

This is **class-level behavior, not joandrew-specific**. The exact
same failure mode can recur for any project:

- An old hermes install path gets removed → agents keep re-memorizing
  the orphan
- A deprecated API key gets deleted → agents keep re-confirming it's
  gone
- A removed plugin gets uninstalled → agents keep re-memorizing the
  uninstall

Every profile is susceptible. The rule belongs in routing because
routing is the always-loaded default, and the rule is a "how to handle
the memory store" discipline that governs every session, not a
project-specific fact.

## The 4-session history (worked example)

| Session | Memory written | What it said |
|---|---|---|
| 2026-06-24 | Multiple | "Hermes dual-dir fact" — `AppData/Local/hermes/scripts/` is `$HERMES_HOME/scripts` |
| 2026-06-24 | 1 | "Hermes kanban dispatcher verified working" — names the AppData board path |
| 2026-07-01 | 1 | "Resolves 103.7.9.47 ... Verify... `C:\Users\somew\AppData\Local\hermes\`" (stale index reference) |
| 2026-07-06 | 1 | "RESEARCH STORAGE ... The path `AppData/Local/hermes` is ORPHANED" |

Each was technically true at write-time. Each was a "verified absent"
fact. None of them STOPPED existing — they kept coming back into
recall, forcing every new session to re-explain "yes, AppData is gone,
no, you shouldn't write there." The user noticed the 4th time.

## The cleanup sequence (worked)

```bash
# 1. Verify absent (multi-path + CLI):
ls /c/Users/somew/AppData/Local/hermes 2>&1 | head -3
ls /c/Users/somew/.hermes/hermes-agent 2>&1 | head -3
which hermes

# 2. Find every Mnemosyne note still encoding the orphan:
mnemosyne_recall(query="AppData Local hermes", limit=20)
# For each hit, classify:
#   - True-forget (encodes the absence/path) → mnemosyne_invalidate, no replacement
#   - Hybrid (rule still valid, only the AppData reference is stale) → update with positive restatement
#   - Unrelated mention (different concept that just happens to cite the path) → keep

# 3. Update hybrid cases with positive restatements:
#   aaa14222d030d3a1 (scraping rule): "don't write hermes-internal" — keep intent, drop AppData
#   e1ae7c9fd1f91531 (research storage): user's 2-place + future Obsidian plan, no AppData mention
#   e5a40cc27bc27338 (profile architecture): 4 profiles + 5 boards was stale; invalidate, add fresh

# 4. Verify nothing in SOUL.md / config / skills still references the path:
grep -r "AppData/Local/hermes" ~/.hermes/{SOUL.md,config.yaml,skills/,hooks/,profiles/*/SOUL.md} 2>/dev/null
# Audit-dump files in .archive/ may keep references; that's historical, leave alone.
```

## The complementary rule: orphan in Mnemosyne is a memory leak

Each re-confirmation of an absent path is a memory leak. Every session
that memorizes "X is absent" is one more session that has to NOT
re-confirm it, but the recall surface keeps surfacing it. The orphan
becomes a noise source: high-importance, frequently recalled, always
pointing at a path the user has confirmed is gone.

The clean fix is true-forget. The Mnemosyne store should reflect the
world the user lives in, not the world they used to live in.

## Cross-references

- `hermes-session-open-inventory` Pitfall #22 ("Verified-absent paths
  should be INVALIDATED, not memorized") — full version of this rule
  with the probe sequence.
- `hermes-session-open-inventory` Pitfall #15 ("ROOTS list is per-host
  not universal", NEW 2026-07-06) — the original orphan-path diagnostic
  that surfaced this pattern.
- `hermes-session-open-inventory/references/orphan-path-true-forget-2026-07-09.md`
  — full worked transcript with all 4 historical memory IDs classified.
- `hermes-misbehavior-diagnosis` — if the agent is still re-memorizing
  the orphan after a true-forget, the diagnose-then-correct pattern in
  this skill catches it.

## Anti-pattern catalog (do NOT do these)

- **Do NOT write a replacement memory** that says "X is now absent" or
  "X was removed on DATE." This is the re-encoding pattern the user
  is rejecting. If you must mention the removal, do it in the session
  output or a session-private scratchpad, not Mnemosyne.
- **Do NOT keep the orphan-reference in a hybrid memory** "just to
  document that we did the cleanup." The reference is the noise. Drop
  the reference, keep the rule's intent, move on.
- **Do NOT use `mnemosyne_remember` to "preserve the orphan
  knowledge"** "in case the path comes back." If the path comes back,
  the next session's filesystem scan will detect it. The Mnemosyne
  orphan is redundant.
- **Do NOT cite the orphan's absence in future output as
  proof-of-cleanup.** "X is gone" is the same statement the user
  rejected. The cleanup is invisible; the absence is silent.
