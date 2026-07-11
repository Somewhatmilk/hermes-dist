# Session-Open Inventory Pitfalls — 2026-07-11 Additions

Companion to `SKILL.md`. Captures four new pitfalls from the 2026-07-11
modularity discussion. When `SKILL.md` is next edited, absorb these as
Pitfalls #20a–#20d (continuing the existing numbering).

## Pitfall #20a — "Write to an existing file" means LIST the candidates

When the user says "write all this info to a file that has other
critical info" / "save to my existing notes" / "put this in the file I
have for X", the response is NOT "create `<new-file>-<date>.md`."

Correct flow:

1. `ls ~/.hermes/docs/ SOUL.md 2>/dev/null` — enumerate candidates
2. For each candidate, scan first ~20 lines for relevance to the topic
3. Propose 1-3 candidate files to merge into, with a one-line justification each
4. Ask the user which one (or whether a new file is genuinely needed)
5. ONLY THEN write — either append to the chosen existing file or create a new one with explicit user confirmation

2026-07-11 failure: user said "write all this info to a existing file
that had otehr crtiical info"; agent wrote
`~/.hermes/docs/hermes-modularity-architecture-proposal-2026-07-11.md`
without listing the existing 3 files in `~/.hermes/docs/` first. The
correct move was to enumerate them and propose appending to
`hermes-environment-reference-2026-07-06.md` (closest topical match —
both install/architecture references).

**Reflex to break:** "user wants file written → write file." The reflex
is correct only AFTER the user has been shown the existing-file
candidates.

**Discriminator question:** "Is there already a file in this host that
covers the same class of topic?" If yes, append-or-propose before
creating.

## Pitfall #20b — Hermes = the FULL stack, not just Mnemosyne

When the user discusses "Hermes" without qualification, they mean the
entire stack: CLI (`~/.hermes/hermes-agent/`), skills
(`~/.hermes/skills/`), mnemosyne, kanban, cron, profiles, config,
mnemosyne plugins, desktop, MCP bridges — not just one layer.

The 2026-07-11 modularity discussion began with the agent over-narrowing
to "the db" (Mnemosyne specifically) when the user meant the 190-skill
library + their interaction patterns.

**Check:** if the user's question touches "Hermes" and any of
{modularity, how things fit, new feature, integration}, default the
scope to the full stack from turn 1. Mnemosyne is ONE layer; the skills
library is ANOTHER; cron is ANOTHER. Treating them as one is the same
failure as "Docker is not available" framing (Pitfall-#10-style layer
collapse).

## Pitfall #20c — After a plan/proposal, START execution on the next turn

The pattern observed across the 2026-07-11 modularity discussion: turn 1
= initial diagnosis, turn 2 = "what we have + gap analysis", turn 3 =
system-prompt-rule evaluation, turn 4 = "write all this info to a file"
(produced a 19 KB architecture proposal doc), turn 5 = "So whats your
supposed plan? ... i think we should do something about existing skills
as i said before" — the user explicitly called out that the agent had
been planning instead of doing across multiple turns.

**Rule:** once a proposal/plan doc exists, the next user turn that
engages with it should be the first execution step, not another
planning artifact.

**Check before writing ANY new doc/proposal:**

- (a) does a doc on this topic already exist in `~/.hermes/docs/`? if yes, append
- (b) is this the SECOND planning artifact on the same topic? if yes, stop planning and ask the user which concrete next action to take
- (c) does the user have to ASK "what's your plan" after I just wrote a plan? if yes, the prior planning turn failed to land

**Anti-pattern:** writing a 19 KB proposal doc, then a condensed summary,
then a scored/optimized meta-prompt response, then ANOTHER summary —
four turns of meta-discussion when the user wanted the agent to start
touching the 190-skill library on turn 2.

## Pitfall #20d — Recommendation-against theories need observed behavior, not theory

On 2026-07-11 turn 3, the user asked "have u validated that 2 can
trigger at the same time" — implying the agent had recommended *against*
a system-prompt rule on theoretical grounds ("skills fire on
description-match, not internal reasoning") but had NOT actually probed
whether multi-skill auto-load worked.

**Check:** any recommendation that says "X doesn't work because the
framework Y does Z" requires EITHER:

- (a) live observation in this session, OR
- (b) explicit caveat "this is theoretical, not observed on this host."

Without one of these, the recommendation is a guess dressed as a finding.

**The trap:** theoretical reasoning about framework internals sounds
confident; users trust it. The honest version is "I haven't probed this
on this host yet — let me check" or "based on prior-session observation
X, the behavior is Y."

**Concrete probe sequence for the 2026-07-11 question:**

1. ask user for a prompt that should trigger multi-skill load
2. observe the loaded-skills list
3. report observed behavior
4. only THEN recommend a fix

This is the same discipline as Pitfall #11 ("user said we have X" ≠
"X is installed") — extend to "I theorized Y" ≠ "Y is true."

## Sandbox-First Workflow (NEW 2026-07-11, this user, this session — explicit user directive)

When a user says "try something new" / "do something about X" / "let me
see if this works" / "experiment with Y", **develop in the sandbox
first, promote to production only after the sandbox version works AND
the user has approved promotion.**

| What you're doing | Where it lives |
|---|---|
| Iterating on a new skill frontmatter | `~/.hermes/sandboxes/<topic>/SKILL.md` |
| Testing a Python script that touches hermes internals | `~/.hermes-state/temp/<date>/` |
| Quarantining an inbound skill from a web scrape | `~/.hermes/quarantine/skills/flagged/` first, `clean/` after validation |
| Patching the live skill library | snapshot first via `~/.hermes-state/snapshots/`, then patch, then verify |
| Experimenting with config.yaml changes | `~/.hermes-state/patches/` as `.yaml.bak` before editing |

**Snapshot before destructive ops.** Pre-edit snapshot →
`~/.hermes-state/snapshots/<topic>__<date>/`. Original `.bak` files
→ `~/.hermes-state/patches/`. Stray files discovered →
`~/.hermes-state/strays/`. This pattern is captured by
`~/.hermes/skills/devops/hermes-state-archive/` — load it before any
destructive op.

**Verify before promoting.** A sandbox skill moves to
`~/.hermes/skills/` only when: (1) `skill_view <name>` loads cleanly,
(2) description doesn't collide with existing skills
(`skills_list | grep` for trigger phrases, not keywords), (3)
frontmatter validates, (4) for risky skills, tested against a fixture.

**The user's exact words (2026-07-11):** *"if possible do it in the
sandbox, test it there as much as u like as many iteration as it
takes."* This is verbatim — it overrides any "iterate in place" reflex.

## Provenance

Captured 2026-07-11 in session `hermes_20260711_160006_491efc`. All
four pitfalls trace to specific user prompts in that session. Pitfall
#20a corresponds to "write all this info to a existing file that had
otehr crtiical info"; #20b to "this doesnt include just the db , i
meant hermes overall"; #20c to "So whats your supposed plan? i think
we should do something about existing skills as i said before"; #20d
to "have u validated that 2 can trigger at the same time". The
sandbox-first rule corresponds to "if possible do it in the sandbox,
test it there as much as u like as many iteration as it takes".