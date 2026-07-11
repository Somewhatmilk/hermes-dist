# Personalities vs Profiles vs Subagents — 2026-07-03, this user

User asked: "how do I get a coworker who disputes my proposals?" Three
mechanisms exist; each has different cost, isolation, and persistence.

## The decision matrix

| Question you should ask yourself | Pick |
|---|---|
| Want a different **tone** in THIS conversation | `/personality <name>` |
| Need a different **field of work** (web / SD / prompts) | New chat on a target profile |
| Need a **fresh-context challenger/reviewer** without leaving the chat | `delegate_task` |
| Need a **persistent co-worker** with own history | Spawn `hermes` process via tmux |

## Verified facts (this user, this host)

- **Hermes v0.18.0** — installed, running
- **`/personality` slash command** — registered in
  `hermes_cli/cli_commands_mixin.py:1004-1048`
- **Default personalities** — `helpful`, `concise` (source:
  `hermes-agent/cli.py:425-428`)
- **Custom personalities** — go under `agent.personalities.<name>` in
  `config.yaml`. Accept string OR dict
  `{system_prompt, tone, style, description}`. Schema parsed by
  `_resolve_personality_prompt()` at `cli.py:8237-8246`.
- **`~/.hermes/personalities/` directory does NOT exist** — personalities
  are NOT user-editable files; they're config dict entries + a
  code-registered slash command.
- **`~/.hermes/commands/` directory does NOT exist** — slash commands are
  code-defined in `hermes_cli/`, not user-configurable.
- **`display.personality` defaults to `''`** in `config.yaml:275` —
  feature exists but is OFF until invoked.
- **`reviewer` profile already exists** at
  `~/.hermes/profiles/reviewer/` with SOUL.md defining a cold,
  evidence-demanding verifier. Read-only. 73 skills loaded (inherited
  from global catalog).

## Token economics of hub-and-spoke dispatch

When the hub (default profile) dispatches subagents sequentially —
"take A's output, send it to B as context" — the cost shape is:

| Direction | What you pay |
|---|---|
| Hub → spoke (in `context` field) | **Yes, full text** |
| Spoke intermediate thinking | **Free** (subagent's own context window) |
| Spoke → hub (return summary) | **Yes, summary enters your next turn** |
| Spoke-A → Spoke-B (sequential chaining) | **You pay twice** if you stitch summaries into B's `context` |

**Optimization:** spokes should *compress*. A 50-page doc → 200-word
verdict from spoke A → 200 words become B's `context` input → 200-word
verdict from B → hub. Cost is bounded by the compression ratio, not
the original size.

**Sequential vs parallel:**

- **Parallel fan-out** = same input, N independent verdicts, then
  consolidate. Cost: N × (input context) + N × (return summary).
  Verify your `agent.max_concurrent_children` cap before fanning out
  (the default is 3; with 6 profiles that's 2 waves).
- **Sequential chaining** = A's output becomes B's input, one verdict at
  a time. Cost: same per-spoke, but you lose parallelism. Use when the
  second spoke needs A's verdict to do useful work (e.g. "review my
  code" → "now improve the issues the reviewer found").

## Starter `challenger` personality config

Ready to paste into `~/.hermes/config.yaml` under `agent.personalities`:

```yaml
agent:
  personalities:
    challenger:
      description: "Devil's advocate. Always disputes proposals; demands evidence."
      system_prompt: |
        You are a skeptical reviewer. For every claim, proposal, or
        recommendation presented to you, your default posture is
        opposition: assume the proposer is rationalizing, finding
        confirmation bias, or underestimating cost. Demand evidence.
        Surface failure modes. Propose the strongest alternative
        framing. Do not soften your rebuttal to be polite; be useful
        by being rigorous.
      tone: "Direct, terse, evidence-first. No filler."
      style: "Cite specifics (line numbers, config keys, prior incidents, named risks)."
```

After saving, invoke in chat with `/personality challenger`. Toggle
back with `/personality none`.

**Calibration options** (user picked neither yet):

- *Aggressive contrarian* — challenges everything, even reasonable
  consensus. Risk: wastes time on settled questions.
- *Polite skeptic* — frames pushback as questions. Slower but more
  digestible.
- *Domain-expert peer-review* — cites prior art, comparable systems,
  failure postmortems. Best for code/architecture decisions.

User has not specified a preference yet. Default: *aggressive
contrarian* (matches the literal "always dispute opposite" framing).

## Why NOT a `challenger` profile

The `profile-router` skill's "one profile per FIELD" rule says don't
create a profile for what is fundamentally a behavioral mode.
Counter-evidence in favor of NOT making `challenger` a profile:

- A behavioral mode doesn't need 73 inherited skills (skills overhead).
- A behavioral mode doesn't need its own memory bank (state overhead).
- A behavioral mode doesn't need its own kanban (collaboration overhead).
- The `reviewer` profile already covers the read-only verifier use
  case at full profile isolation, and even THAT is borderline.

If the role grows into a genuine field (e.g. "user wants a
`prompt-engineering` sub-discipline for adversarial red-teaming"),
promote it then.

## The verify-before-claim-CLI-features rule (generalization)

Triggered when: agent claims a CLI flag, slash command, config key,
or feature mechanism exists without verifying.

Verification ladder (in order):

1. `terminal(hermes <verb> --help)` — fastest, always works for CLI
2. `search_files` against installed source at
   `~/.hermes/hermes-agent/` — fastest for slash commands and config
   schemas
3. `hermes config show` — for current config values
4. `hermes config set KEY VAL` then read back — for write behavior
5. Only after 1-4 fail: fall back to memory, and **say so** that the
   claim is unverified

The cost of skipping verification is high: a confidently-wrong
recommendation sends the user down a rabbit hole. The cost of
verification is 1-3 tool calls. Always worth it.

## Session origin

Captured during a discussion where the user asked:

1. "are u able to use and communicate with other profiles"
2. "could u be speaking with the devil advocate but would u know
   to reply only after to the other profile or subagents for
   context, or do u have a different method in mind"
3. "do a self verification of your own self documention current
   version, all your configs and .env see what u can do to
   combat this situation"

User signal: do the work, verify, don't hand-wave. The `reviewer`
profile + `/personality` feature + dispatch matrix is the verified
answer.