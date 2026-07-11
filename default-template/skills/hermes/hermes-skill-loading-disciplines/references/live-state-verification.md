# Live-state verification for Hermes architecture questions

## The rule

When a user asks "is X an actual Hermes file?" or "does the runtime
read Y?" or any question about which files/schemas/keys exist in
Hermes — **load the relevant skill first, then probe live state, then
answer.** Do not answer from training data, from a recovered subagent
report, or from narrative. The user expects evidence-backed answers.

## What triggers this rule

Any of these phrasings (not exhaustive — the principle is "Hermes
internals question"):
- "is this a actual file used by hermes or created"
- "where does X live in hermes"
- "what reads Y"
- "should I move Z"
- "where should I put W"
- Any question naming a specific path under `~/.hermes/`

## Pre-flight sequence (do all four, in order)

1. **Load the relevant umbrella skill.** Most likely candidates:
   - `hermes-profile-taxonomy` — for any question about profile files
   - `hermes-agent` — for any question about the CLI/agent runtime
   - `session` — for memory, sessions, persistence
   - `hermes-profile-dispatch-rules` — for dispatch, profile selection
   - `hermes-skill-loading-disciplines` — for "should I load a skill?"
2. **`ls` the actual paths** the question references. `find` for
   related files. `cat` the file content (it's user config, not secret).
3. **Grep the Python source** for the symbol/key/path the user asked
   about. `grep -rnE "key_name" ~/.hermes/hermes-agent/agent/ ~/.hermes/hermes-agent/hermes_cli/ ~/.hermes/hermes-agent/gateway/` is the
   standard probe.
4. **Cross-check recovered subagent reports against live state.**
   Subagent reports can be comprehensive and still miss things. The
   2026-07-06 voice refactor subagent report was 20.7 KB and
   line-cited, but it documented only TWO files per profile
   (config.yaml + SOUL.md) and missed `profile.yaml` entirely. The
   user caught the gap. **Subagent evidence is hypothesis, not canon.
   Live state is canon.**

## Pattern from a real session (2026-07-06)

User asked: "there is profile.yaml doesnt it take the role of role in
soul.md but i was wondering if this is a actual file used by hermes or
created and should we move it?"

I had not loaded `hermes-profile-taxonomy`. I had been working from a
recovered subagent report (correct about `display.personality` vs
`agent.system_prompt`, wrong about the file inventory). I went to live
state on the user's prompt and found 7 `profile.yaml` files I had
missed, plus a duplicate-file bug on the default profile. The
corrected answer was: profile.yaml is real, the loader reads it, the
duplicate is a bug, and the schema has THREE files per profile (not
two).

If I had loaded `hermes-profile-taxonomy` at session start (or at the
first profile-file question), the answer would have been correct on the
first turn.

## What NOT to do

- Do not answer "X doesn't exist" without `ls`/`find` proving it.
- Do not answer "X is read by Y" without a code citation.
- Do not answer "this is the schema" without `cat config.yaml` showing
  the actual keys.
- Do not synthesize an answer from a subagent report when the user is
  asking about something the report might have missed.
- Do not skip live state because the question seems "obviously"
  answerable from training data. The user's installs are custom; the
  defaults may not match.

## What TO do

- Run `ls` and `find` in parallel with `cat` and `grep` — they're
  independent reads, batch them.
- When a subagent report contradicts live state, live state wins. Flag
  the drift to the user.
- When a subagent report is silent on a question, that's NOT evidence
  of absence. Verify.
- When you find a bug (e.g., duplicate profile.yaml), say so directly.
  Don't paper over it.

## Trigger: when to load this reference

- Any question about which files Hermes has
- Any question about what reads a key/path/file
- Any time a subagent report is in play and the question is about
  something the report didn't address
- Any time the user uses phrasing like "is this real" or "is this
  actually used"
