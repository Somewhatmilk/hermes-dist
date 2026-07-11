# Anti-pattern: Predicting a cause without running the diagnostic that would verify it

**Status:** NEW 2026-07-09, this user. v2.7.0 candidate for `hermes-misbehavior-diagnosis`.
**Family:** positive-claim cousins. Sibling to `claiming-credit-for-an-edit-you-didn't-make`
(the agent claims it edited X without verifying on-disk), `bug-hypothesis-before-canon-check`
(the agent hypothesizes a NEW BUG without reconciling against just-loaded canon),
and `investigation-as-narration` (the agent narrates the diagnosis instead of answering).

## The pattern

The agent has a file. It has a hypothesis about the file's behavior. The
hypothesis is plausible — passes a "smell test" against the function names,
the docstring, the comment chain. **The agent then predicts the behavior
without running the test that would actually reveal it.** Predictions are
issued as confident next-steps: "uncomment this, restart, and it'll work"
or "managed_env is clobbering on the second call." When the prediction
proves wrong, the agent issues a *second* prediction in the same shape,
and may issue a *third*.

This is the **Class 1 / Class 2 failure** the conversation explicitly
called out: a confident wrong prediction, followed by another confident
wrong prediction in the same session, before the agent finally runs the
diagnostic that would have caught both at once.

## The 2026-07-09 incident (this user)

**Setup:** Hermes desktop was throwing 401 on Telegram adapter calls.
The 401 was reported as "pass:api/telegram-bot was rejected by the server"
in earlier `gateway-stdio.log` lines — i.e. the literal `pass:...` string
was reaching Telegram's auth service.

**The agent's first prediction (WRONG):** "The 8 `pass:api/X` lines in
`~/.hermes/.env` are commented out. Uncomment them, restart, the 401
will go away." The user approved the uncomment. The 401 did not go
away.

**The agent's second prediction (WRONG):** "It's the managed_env
loader. The 4-call sequence in `load_hermes_dotenv` calls
`_load_dotenv_with_fallback(managed_env, override=True)` AFTER the user
env, and managed scope has its own `TELEGRAM_BOT_TOKEN=` set to empty,
clobbering the user env's `pass:api/telegram-bot`." This was a
plausible-looking hypothesis. **The agent did not read the managed_env
to verify it had such a key, and did not run a single test to see what
`os.environ['TELEGRAM_BOT_TOKEN']` actually contained after a
`load_hermes_dotenv()` call.** The user had to push back: *"u know
what can u simulate opening hermes desktop or any hermes application
and verify all pointers in fact actually load?"*

**The actual test the agent finally ran:** a fresh Python process that
imported only `dotenv` (not `hermes_cli.env_loader`), called
`load_dotenv` on `~/.hermes/.env`, then imported
`agent.secret_sources.pass_source` and called `resolve_dotenv_pointers`
on the same file. **This single test (test S in the session transcript)
revealed in 30 seconds that all 7 pass-pointers resolve correctly when
the loader is run from a cold process — i.e. the bug is NOT in the
resolver, NOT in the `.env` content, and NOT in managed scope. The bug
is in `_APPLIED_HOMES` cache pollution at `hermes_cli/env_loader.py:319`:
the early-return on cache hit means the pass resolution step silently
no-ops whenever a sibling import has already populated the cache.**

**Cost of the two wrong predictions:** ~6 turns of debugging chasing
the wrong layer. The correct diagnosis (`_APPLIED_HOMES` cache hit →
pass resolver no-ops → adapters see literal `pass:api/X` strings →
401) was findable in 2 turns with a cold-process test.

## Why this is distinct from the other anti-patterns

| Anti-pattern | What's claimed without verification |
|---|---|
| `claiming-credit-for-an-edit-you-didn't-make` | "I added/fixed/patched X in this session" |
| `bug-hypothesis-before-canon-check` | "X is a NEW BUG" (contradicts just-loaded canon) |
| `investigation-as-narration` | The diagnostic journey itself, as filler for the answer |
| **This pattern (NEW 2026-07-09)** | **"Y will fix the symptom" — predicting a fix's effect without running the test that would show the effect** |

The shape is: the agent has a fix. The fix is plausible. The agent
*recommends* the fix (or applies it) **before** running the test that
would distinguish "this fix works" from "this fix is cosmetic." The
test exists, is fast, and would have been decisive — but the agent
chose to predict instead.

## The operational rule (encode in SKILL.md pitfall)

**Before issuing a "this will fix X" prediction, name the test that
would prove or disprove it. If the test takes < 60 seconds to run, run
it. If you can articulate the test but not run it (e.g. needs a
gateway restart the user controls), say "this should work, but I
can't verify without restart — the test is <this>."**

The corollary: if you find yourself issuing a SECOND "this will fix X"
prediction in the same session after the first one didn't work,
**stop and audit your prediction methodology, not the next hypothesis.**
Two wrong predictions in a row is strong evidence the prediction loop
is broken (the agent is fitting the symptom to a hypothesis instead of
running the test). The right move is: cold-process repro, fresh
hypothesis, or escalate to the user with the test that would resolve it.

## When the rule does NOT apply

- Trivial single-line fixes where the test cost exceeds the fix cost
  (e.g. "add a log line and restart" — the test is the restart, the
  fix is one line, ship it).
- Fixes gated behind a hard-to-replicate runtime (e.g. "defer this
  fix to the user, they have to test in their actual environment").
- Pure documentation changes (no code, no runtime surface).

The rule fires when the agent's *first move* on a reported bug is
"here's what I think is wrong and here's the fix" without "here's the
test I ran that showed me." If the test would take 60 seconds, run it
first.

## User pushback phrasing that should fire this reflex

- "u know what can u simulate opening hermes desktop or any hermes application and verify all pointers in fact actually load?"
- "did u actually run that or just predict it?"
- "did u test this fix before recommending it?"
- "two wrong predictions in a row — what's your test methodology?"
- "show me the test that would have caught this"
- "u keep guessing, run the test"
- "the whole point of this was so i didn't need to do plaintext and clean mnemosyne too" (2026-07-09, this user — when the agent offered "build a wrapper around the .cmd" or "resolve to plaintext in .env" as fix options for a "literal pass:api/X reached the platform" symptom, instead of pointing at the framework's existing dynamic resolver)
- "ididnt need to do plaintext" (2026-07-09 — same instance, second phrasing)

**Self-tic phrases** (the agent's own narration when it's about to
predict without testing):
- "this should work because..."
- "the fix is to..." (without "I tested and...")
- "let me predict the cause"
- "here's my hypothesis"
- "I bet it's..."
- "if X then Y"

When the agent's next sentence starts with one of these, the
operational reflex is: *name the test, run it, THEN write the
prediction.*

## Companion diagnostic recipe

The cold-process test that broke this case open in 30 seconds:

```python
# In a brand new Python process — no Hermes imports.
import os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=str(Path.home()/'.hermes'/'.env'),
            override=True, encoding='utf-8')
# State of os.environ right after python-dotenv runs.
for n in ['TELEGRAM_BOT_TOKEN', 'DISCORD_BOT_TOKEN', ...]:
    print(f'  {n:32s} = {os.environ.get(n, "<UNSET>")}')

# Now call the resolver directly. No caches, no guards.
sys.path.insert(0, '/path/to/hermes-agent')
from agent.secret_sources.pass_source import resolve_dotenv_pointers
r = resolve_dotenv_pointers(Path.home()/'.hermes'/'.env')
print(f'applied={r.applied} skipped={r.skipped} '
      f'warnings={r.warnings} error={r.error}')

# State of os.environ after resolution.
for n in [...]:
    print(f'  {n:32s} = {os.environ.get(n, "<UNSET>")[:20]}...')
```

**If this test shows the resolver works (applied > 0, no errors), the
bug is NOT in the resolver.** The bug is in whatever sits between
this test and the live boot — most commonly cache pollution (the
`@functools.lru_cache`, the module-level `_APPLIED_HOMES` set, the
`@lru_cache(maxsize=1)` on a config loader). The recipe isolates the
"isolated module" from the "integrated boot" so you can see which side
of the boundary the bug lives on.

This recipe is also captured as a verification ritual in
`hermes-config-cli-gotchas/references/pass-resolver-cold-start-test.md`.
The two references cross-link so future sessions can pick up either
side of the lesson (the misbehavior reflex vs the diagnostic recipe).
