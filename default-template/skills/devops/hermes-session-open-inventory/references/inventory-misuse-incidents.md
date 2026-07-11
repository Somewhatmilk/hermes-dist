# Inventory Misuse Incidents (2026-06-26)

Session transcripts where the multi-path + trichotomy verification was needed and would have caught the failure. Capture the failure shape so future sessions recognize it.

---

## Incident 1 — "We ran this yesterday" (GEPA / `evolution.skills.evolve_skill`)

**Context.** Session opened with the agent about to write a new skill called `prompt-evolve-loop` (a GEPA orchestration skill). The skill's only prerequisite was `evolution.skills.evolve_skill` being installed.

**Memory recall result.** A Mnemosyne row scored 0.77 (high): importance 0.95, recall_count 18, fresh timestamp (2026-06-26 00:14, ~10 hours prior), veracity `tool`. The row said "GEPA self-evolution pipeline — 2026-06-25 fabrication incident + real fixes," described a v3-v9 progression including a "v7 patch" that fixed `RelevanceScorer`/`RelevanceFilter` auth, and referenced 1328 messages of context.

**What the agent did wrong.** Treated the memory as ground truth. Wrote the skill assuming the tool existed. The skill's Prerequisites section read:

> "A working `evolution.skills.evolve_skill` invocation (the `RelevanceScorer` / `RelevanceFilter` auth fix must be in place — see 2026-06-25 patch)"

**What the user caught.** After the skill was written, the user requested a smoke test. The agent ran `hermes evolution.skills.evolve_skill` and got:

```
hermes: error: argument command: invalid choice: 'evolution.skills.evolve_skill'
(choose from 'chat', 'model', 'fallback', ..., 'profile', ...)
```

The agent then concluded "GEPA isn't installed, skill is dormant" — and shipped the skill anyway with a vague "if not, the skill is dormant" disclaimer.

**What was actually wrong with that diagnosis.**

1. **`hermes evolution.skills.evolve_skill` is the wrong CLI.** There is no `hermes evolution` subcommand. The actual invocation is `python -m evolution.skills.evolve_skill`, with `evolution` being a pip-installed editable package under `hermes-agent-self-evolution/`.

2. **The tool WAS installed.** Multi-path scan revealed it at:
   - `C:\Users\somew\AppData\Local\hermes\hermes-agent-self-evolution\` (the repo)
   - `C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\__editable__.hermes_agent_self_evolution-0.1.0.pth` (pip editable marker)
   - `C:\Users\somew\AppData\Local\hermes\hermes-agent-self-evolution\evolution\skills\evolve_skill.py` (the actual module)
   - `C:\Users\somew\AppData\Local\hermes\hermes-agent-self-evolution\evolution\core\external_importers.py` (the scorer)

3. **The agent had checked only ONE path** (`hermes-agent/agent/` and `hermes-agent/`) and missed the **sibling directory** `hermes-agent-self-evolution/`.

**The user's exact pushback (verbatim):**

> "alot of the times either from past session or test the tool isnt installed but check for the last session why did it assume it was installed? and we need a better validation check for installation for stuff like this OR its in a dir somewhere else and u just checked 1 path and assume it deosnt exist and run the question proceed"

**The fix.** Wrote `hermes-session-open-inventory` skill + `verify_tool_installed.py` utility. The utility scans 5 verified roots, checks CLI reachability, cross-references Mnemosyne recall, and produces a 3-state trichotomy (verified_present / verified_absent / unverified) for each known tool.

**Result on the same session, after the fix:**

```
SESSION-OPEN INVENTORY (2026-06-26 10:52:33)
[OK] GEPA / evolution.skills.evolve_skill           -> verified_present
[OK] external_importers.py (GEPA scorer)            -> verified_present
[OK] hermes CLI                                     -> verified_present
[OK] Mnemosyne                                      -> verified_present
[OK] DSPy (in venv site-packages)                   -> verified_present
[OK] GEPA standalone library                        -> verified_present
SUMMARY: present=6  absent=0  unverified=0  unknown=0
```

12 seconds end-to-end. Patched `prompt-evolve-loop`'s Prerequisites + Step 0 to use the new utility before invoking GEPA.

---

## The two root causes (generalize, don't memorize)

The GEPA incident had two distinct failures. Both are class-level. Future sessions should recognize either:

### Root cause A — Memory recall ≠ ground truth

A Mnemosyne row with high confidence score, importance 0.9+, fresh timestamp, and `veracity: tool` describes what a prior session claimed. **It is not evidence that the claim is true right now.**

Discriminator:

| Memory phrasing | What it is | Cite as live? |
|------------------|------------|---------------|
| "Ran `python -m evolution.skills.evolve_skill` on 2026-06-25" | Past session verb | **No — past action, not current state** |
| "GEPA returned 150/150 errors" | Past tool output | **No — that output was from a prior session** |
| "External_importers.py is at C:\Users\somew\..." | File path claim | **No — file may have been moved, deleted, or never installed here** |
| "We have 5 profiles: default, communicate-design, ..." | Current stack claim | **No — verify with `hermes profile list`** |

This is the same pattern as the `session` "Live state is the source of truth" rule, applied to tools/skills/repos instead of containers/processes.

### Root cause B — One-path verification is not verification

Searching only `hermes-agent/` for a tool and concluding "not installed" when the tool lives at `hermes-agent-self-evolution/` is **wrong**. Both are children of `hermes-home/`. The search missed the sibling.

Common sibling/child miss patterns on this host:

| Canonical location | Common misses |
|--------------------|---------------|
| `hermes-home/hermes-agent/` (app source) | Searching only `hermes-home/agent/`, `hermes-agent/agent/`, `hermes-agent/src/` |
| `hermes-home/hermes-agent-self-evolution/` (GEPA repo) | Searching only `hermes-home/`, `hermes-agent/`, or assuming GEPA must be inside `hermes-agent/` |
| `hermes-home/default/` (default profile) | Searching only `hermes-home/profiles/default/` |
| `hermes-home/skills/` (cross-profile shared) | Searching only `hermes-home/profiles/*/skills/` |
| `~/Documents/hermes-research/` (long-term research) | Searching only `~/Documents/` recursively without filtering |
| `~/Downloads/One-Cut-Deeper/` (legacy OCD) | Assuming it's gone because the user moved to `hermes-research/` |

**Rule: minimum 5 roots** for any tool/repo install check on this host:

```python
ROOTS = [
    Path(r"C:\Users\somew\AppData\Local\hermes"),
    Path(r"C:\Users\somew\AppData\Local\hermes\hermes-agent"),
    Path(r"C:\Users\somew\AppData\Local\hermes\hermes-agent-self-evolution"),
    Path(r"C:\Users\somew\Documents\hermes-research"),
    Path(r"C:\Users\somew\Downloads\One-Cut-Deeper"),
]
```

`verify_tool_installed.py` already encodes this list. Don't reinvent it inline.

---

## Anti-pattern catalog

Each is something that fired (or would have fired) in a real session, with the lesson.

### Anti-pattern 1: Memory recall + one filesystem check → "verified"

> "I have a memory that GEPA is installed, and I see hermes-agent/ exists, so GEPA must be in there somewhere."

This was the exact pattern that produced the wrong "GEPA not installed" conclusion. Memory is a hypothesis. `hermes-agent/` is one of ~6 places the tool could live. **Both** must be checked against **multiple** candidate paths, and the candidate set must include sibling dirs.

### Anti-pattern 2: Ship the skill with a "dormant" disclaimer

> "The skill might not work if X isn't installed, but I'll write the invocation pattern anyway."

A skill that prescribes an invocation is making a **factual claim** about the tool's presence. Either verify the claim or write the skill to be **conditional** on the verification result. A "dormant infrastructure" disclaimer is a way to ship wrong work without owning it. The user reads "dormant" as "we'll fix later"; the next session reads it as "I already verified, just run it" and ships the wrong work again.

The fix: write skills whose first line is "Run `verify_tool_installed.py --tool X --strict`. If exit 1, stop here. If exit 0, continue."

### Anti-pattern 3: Conclude "absent" from one negative hit

> "I searched hermes-agent/ for `evolve_skill.py` and didn't find it. The tool isn't installed."

Single-path negative searches are not absence proofs. The tool could be at:
- `hermes-agent-self-evolution/` (sibling)
- `hermes-home/skills/` (cross-profile shared)
- A venv site-packages (if pip-installed editable)
- An `importlib`-resolved location different from the visible source path

**Rule: a "verified_absent" state requires checking at least 3 paths, including the canonical home, the canonical sibling, and at least one venv/site-packages candidate.**

### Anti-pattern 4: Trust the CLI subcommand name from memory

> "It's `hermes evolution.skills.evolve_skill`, I think. Let me try."

Wrong. The actual invocation is `python -m evolution.skills.evolve_skill`. `hermes evolution` is not a subcommand. The `--help` flag is the cheap verification: `hermes evolution --help` returns "invalid choice" if the subcommand doesn't exist; `python -m <module> --help` returns proper usage if the module is importable. **Always run the actual command's `--help` before claiming the invocation pattern.**

### Anti-pattern 5: Forget the cross-profile / cross-env seam

A tool installed in `prompt-engineering` profile's venv might not be importable from `default` profile's runtime. A pip-installed editable package in `hermes-agent/venv/` might be on disk but the venv's `python.exe` might be different from the one the agent invokes. The CLI verification (`python -m X --help`) catches this if you actually run it. The file-existence check does not.

`verify_tool_installed.py` runs both: filesystem scan (catches on-disk installs) AND CLI verification using the canonical `hermes-agent/venv/Scripts/python.exe` (catches importable installs).

---

## Cross-reference

- `verify-before-claim-hardware` skill — same anti-pattern class, applied to hardware/system state. Patched 2026-06-26 to add the "tool/repo INSTALLATION variant" section.
- `session` step 11 — "Verify before claiming TOOL INSTALLATION" added 2026-06-26 with the multi-path + trichotomy reference.
- `prompt-evolve-loop` pitfalls — "VERIFY-BEFORE-PRESCRIBE" added 2026-06-26 with the verbatim user pushback.
- Memory `af699f1a` (validated/updated 2026-06-26) — the GEPA fabrication-incident memory, with the corrected framing (the fabrication risk was about fake score numbers, not about the tool's existence).
- Memory `62420df9` (added 2026-06-26) — captures the lesson explicitly: "ALWAYS scan a multi-root set: hermes-home, hermes-agent, hermes-agent-self-evolution (sibling), hermes-research, Downloads/One-Cut-Deeper."