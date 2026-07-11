# Mnemosyne Recall Discipline

Mnemosyne is best-effort: recall returns what's been written, ranked by score, not what's still true. This reference covers (a) deciding whether to trust a recalled fact, (b) choosing the right action when recall is stale or contradicted, and (c) writing replacements that don't keep the stale version alive.

## When to load this

- User says "your memory is wrong about X", "is there a way to forget?", "you keep using outdated context"
- A recall returns multiple facts with similar importance scores that disagree (importance tie)
- A recall returns a fact dated earlier than a contradicting fact the user just stated
- Before acting on a recalled fact for a state-changing operation (config edit, profile rename, ticket routing)

## The 4-state staleness matrix

When recall surfaces a fact, classify it on two axes:

| Axis | Question | Values |
|---|---|---|
| **Time** | Is there a more recent fact on the same subject? | unique / superseded-by-newer / contradicted-by-newer |
| **Authority** | Is the recalled fact the latest user-stated intent, or an older belief? | user-stated / derived / inferred / observed |

Decision tree:

```
Is there a newer fact on the same subject?
├── NO  → trust the recall, proceed
└── YES
    ├── Is the newer fact from the user? (user-stated beats everything)
    │   ├── YES → trust the newer fact, invalidate the older
    │   └── NO  → both might be derived; check timestamps and provenance
    └── Same-importance tie?
        ├── Recency wins (always)
        └── If still ambiguous, ask the user
```

## The recency-as-tie-breaker rule

**When two memories have the same importance score on the same subject, the more recent one wins.**

Mnemosyne's recall scores by `vec + FTS + importance` (0.5/0.3/0.2 weighted). When two memories tie on importance but differ on timestamp, the **score-weighted ordering is wrong** — it can let an older, higher-similarity-but-stale memory outrank a newer, explicit-supersede statement.

**Real failure mode (this host):** recall for "joandrew owner profile" returned two memories at `importance: 0.95`:
- 2026-06-24 13:40: "web-designer = joandrew manager" (older, longer content, denser vector match)
- 2026-06-24 14:02: "communicate-design owns joandrew; web-designer was deleted" (newer, explicit supersede)

The agent picked the older one and got the assignee wrong.

**Rule for recall consumers:**
1. Scan results for "supersede / now owns / was deleted / no longer" patterns. When present, the supersede-statement wins regardless of score.
2. Sort same-importance ties by timestamp descending before reading them.
3. If a recall returns N memories that disagree, the fact is contested — don't pick the highest-scoring one; pick the one whose content matches the most-recent prior turn, or recurse to live CLI to settle.

**Rule for memory writers:** when a fact changes, write the new fact AND a "supersedes" pointer to the old one. Example: `mnemosyne_remember("X is now the owner; supersedes web-designer (deleted 2026-06-24)", importance=0.95, source="correction")`. The "supersedes" keyword helps future recall consumers disambiguate.

## The 4 actions: invalidate vs forget vs supersede vs verify

| Action | When | Tool | Reversible? |
|---|---|---|---|
| **invalidate** | Fact is wrong but the historical context matters (audit trail). Row stays in DB, hidden from recall. | `mnemosyne_invalidate(memory_id=...)` | Yes — can be re-validated |
| **forget (hard delete)** | Fact is wrong AND was never useful in any context (test data, hallucinated output). | `mnemosyne_forget(memory_id=...)` | No |
| **supersede** | Newer fact supersedes older fact on the same subject. Write new first, then invalidate old with `replacement_id` pointing to new. | `mnemosyne_remember` + `mnemosyne_invalidate(replacement_id=...)` | Yes |
| **verify** | Fact might be right; need live confirmation before acting (config claim, profile ownership, ticket state). Don't touch memory — check disk/CLI/state directly. | `hermes <cmd>`, `read_file`, `terminal` | N/A |

**Default action:** `invalidate` with `replacement_id` set to the newer fact. Safest because it preserves audit history while suppressing the stale row.

> **⚠️ CRITICAL CAVEAT — canonical entries bypass this entire table.** The 4 actions above apply to the `private` and `surface` memory banks. Canonical entries (the ones written via `mnemosyne_remember_canonical`) are stored in a different bank and cannot be invalidated, forgotten, or validated by these tools. **For canonical supersede, see the dedicated section below.** The agent's instinct of reaching for `invalidate` when the user says "that memory is wrong" is wrong for canon.

## Pre-action verification protocol

**Before any state-changing operation that depends on a recalled fact, verify against live state.** Mnemonic: "memory is a *cache*, not the source of truth."

The 4-step protocol:

1. **Recall** — `mnemosyne_recall(<subject>, limit=5)` — get the candidate facts.
2. **Classify** — apply the staleness matrix. Find the authoritative fact.
3. **Verify** — for state-changing operations, run the live check:
   - Profile ownership → `hermes profile list` (profile directory on disk is truth)
   - Ticket state → `hermes kanban show <id>` (DB is truth)
   - Config value → `hermes config show` or read `config.yaml` directly
   - Memory fact about a person/project → ask the user
4. **Reconcile memory** — if live state contradicts the recalled fact, invalidate the stale memory. If they agree, no action.

**Triggers for mandatory pre-action verification:**
- Renaming or deleting a profile
- Routing a kanban ticket to a profile
- Editing config.yaml or .env based on a remembered value
- Citing a past decision as justification for the current one
- Reusing a path or URL from memory

**Cost:** 1-2 seconds per `terminal` call, occasionally 1 user clarification. **Benefit:** eliminates the entire class of "agent cited a stale fact and did the wrong thing" failures.

## Verify `memory_id` against `content_preview` before any mutation

Recall returns `(memory_id, score, content_preview, ...)` tuples. **The ID is opaque. The `content_preview` is the only handle to verify you're mutating the right row.**

**Real failure mode (this host):** the agent needed to invalidate a stale fact (joandrew → web-designer). Recall returned the stale fact as the top result, and a related dispatch-gotcha memory right after. The agent used the first ID returned without checking the preview, and silently killed the dispatch-gotcha memory instead of the stale fact. The content_preview would have shown which was which in under a second.

**The 3-step mandatory verify for `mnemosyne_invalidate`, `mnemosyne_forget`, `mnemosyne_update`:**

1. **Read the preview.** Does it match what I think I'm mutating? If not, **STOP**. Re-call recall with a more specific query until you have a preview that matches.
2. **If the preview matches, run the mutation.**
3. **Immediately re-recall to verify** the row is gone (for invalidate/forget) or has the new content (for update). If verification fails, restore via `mnemosyne_remember` (for forget/invalidate accidents) or retry.

**Why this isn't paranoia:** Mnemosyne's invalidate is **soft** (preserves row, suppresses from recall), but in the wrong row it permanently suppresses a useful memory. Forget is **hard delete** — wrong row = data loss. Update silently returns `not_found` for the integer-ID vs hex-ID confusion. Every mutation is destructive; every mutation deserves the 3-step verify.

## The 2-pass filter rule

**When narrowing recall results, do not assume a filter dimension exists on the recall API.** Mnemosyne's `beam.recall()` (v3.10) accepts a fixed kwarg set — adding an unsupported filter silently no-ops or raises mid-call, and the agent invents a reason the recall "didn't find" the target fact.

**Mnemosyne v3.10 `beam_recall` public kwargs (verified):**

| Kwarg | Type | Default | What it does |
|---|---|---|---|
| `query` | str | (required) | Hybrid-searched across FTS5 + vector |
| `limit` | int | 5 | Max results |
| `recency_weight` | float 0-1 | 0.3 | Bias toward newer memories |
| `min_importance` | float 0-1 | 0.0 | Filter below this importance |
| `include_invalidated` | bool | False | Surface soft-deleted memories (audit) |

There is NO `source=`, `source_type=`, `domain=`, `tag=`, `time_range=`, `after=`, `before=`, `created_by=`, `session=`, or `episodic=` parameter on the public surface. To filter by any of these, do a broad recall and filter the result list client-side.

**The rule:**
1. **First recall call: maximum-broad, smallest filter set.** Use the dimensions guaranteed to exist: `query`, `limit`, `recency_weight`, `min_importance`.
2. **Inspect what came back.** The response shape tells you which post-filters to apply client-side: scan `source`, `timestamp`, `importance`, `content_preview` of each result. **These fields are the API.** A "domain" filter is `if source == "domain-x"` after the recall.
3. **Only add recall kwargs whose existence you can verify in the source.** If you can't quote the line in `mnemosyne/core/beam_search.py`, don't pass the kwarg.

**Client-side post-filter pattern:**

```python
results = mnemosyne_recall("auth config", limit=20)
auth_only = [r for r in results if r.get("source") == "domain-codebase"]
# or
recent_only = [r for r in results if r.get("timestamp", "") > "2026-06-01"]
# or
above_threshold = [r for r in results if r.get("importance", 0) >= 0.7]
```

This is more reliable than trying to push filters into the recall call AND it surfaces the full result set so you can see what was filtered out.

**Verify signature before designing against it:**

```bash
python -c "
from mnemosyne.core.beam_search import beam_recall
import inspect
print('signature:', inspect.signature(beam_recall))
print('docstring:', (inspect.getdoc(beam_recall) or '(none)').splitlines()[:5])
"
```

The signature IS the API. The docstring IS the contract. If your designed workflow needs a parameter that isn't in either, the workflow is wrong — refactor it to use the parameters that DO exist plus client-side filtering, or call a different function entirely.

## Diagnostic sequence before any recall-dependent action

```
1. mnemosyne_recall(<subject>, limit=5)
2. For each returned fact, note: timestamp, importance, source (user-stated vs derived)
3. Find the most recent user-stated fact on this subject
4. If a state-changing operation is coming, verify live:
   - terminal("hermes <relevant-cmd>")  OR  read_file(<relevant-path>)
5. Apply staleness matrix; pick action (invalidate / supersede / verify-only / no-op)
6. If invalidating, READ the row first to confirm you're nuking the right one
7. In a single batch: invalidate the old + remember the new (with replacement_id) — atomic
8. Reply WITHOUT restating the stale fact in plain text
```

## Don'ts

- **Don't trust importance over recency.** Importance is "how much should this matter," not "is this still true."
- **Don't write a new memory without invalidating the old one** (when on the same subject). Both rows compete in recall; future recall returns both, the agent picks one (probably higher-importance = stale), same failure.
- **Don't `forget` unless you mean hard delete.** `invalidate` is almost always right.
- **Don't claim a memory is wrong without checking the disk.** The user might be remembering wrong, or there might be a third fact Z.
- **Don't batch-invalidate without reading each row.** `mnemosyne_invalidate` is per-ID. The "I'll just invalidate the top hit" shortcut often nukes the wrong row.
- **Don't re-state the stale fact in your reply before invalidating.** The reply is logged; the string gets re-recalled later. Phrase corrections as "the latest fact says X; the older Y is invalidated."
- **Don't reach for `invalidate`/`forget`/`validate` on a canonical entry.** Those tools don't touch the canonical bank. Reach for `mnemosyne_remember_canonical` to the same slot. (See "Canonical entries: supersede at the slot" below.)
- **Don't conclude "can't be done" after one tool returned a rejection.** The rejection is a signal about the right tool — read it, find the documented alternative, try it. (See "The 'I tried it, it didn't work, give up' antipattern" below.)

## The 3-way decision matrix (invalidate vs forget vs supersede-pointer)

| Situation | Right response | Why |
|---|---|---|
| Fact is wrong AND was always wrong | `mnemosyne_forget` (hard delete) | No audit value; soft-deleting adds recall noise |
| Fact was right at the time, superseded by newer | `mnemosyne_invalidate` with `replacement_id` pointing to new fact | Preserves audit trail |
| Fact was right, still right, but needs re-statement | Add "supersedes" pointer in new memory; **leave old one** | Reader sees lineage in one lookup |
| Fact is a duplicate of an existing one | `mnemosyne_validate --action invalidate` with `canonical_id` of original | Idempotent; won't touch unrelated entries |
| Fact is sensitive (credential leak, was a mistake) | `mnemosyne_forget` AFTER backup `cp mnemosyne.db mnemosyne-pre-sweep-<ts>.db` | Sweep deletes are irreversible; backup is rollback |

**Default:** prefer `invalidate` over `forget` unless the memory has zero audit value.

## Stop-rule memories are highest-risk

A memory that says "do NOT do X" must be re-verified against live state before it's acted on. The user changes their mind; the memory becomes a permanent hallucinated veto.

**Real failure mode (this host):** a memory entry said "do NOT remove legacy Documents/ content, user is preserving for reference." The agent almost concluded "don't move the uniques, don't delete the legacy." A `diff -rq` against live state showed the legacy was already mostly empty (only 2 small unique items, both mirrored in AppData). The memory was stale; the user's current instruction ("move uniques, delete legacy") was correct.

**Fix:** when a memory says "do NOT do X" and the user's current instruction is to do X, run the live state check first, then either invalidate (if X has clearly been done already), supersede (if X is now permitted), or ask (if genuine ambiguity).

## Canonical entries: supersede at the slot, do NOT annotate around them

**The 4-action table at the top of this reference is wrong for canonical entries.** The `mnemosyne_invalidate`, `mnemosyne_forget`, and `mnemosyne_validate` tools operate on the `private` and `surface` memory banks ONLY. **They do not touch the canonical bank** (the one written to via `mnemosyne_remember_canonical`). Calling them on a canonical-slot ID returns `memory_not_found` or `bank_invalid` — the entry stays in the canonical bank, active and at full recall strength.

**The right tool is `mnemosyne_remember_canonical`** — written to the same `(category, name)` slot the stale entry lives in. Per the schema, "a new body supersedes the old one (kept as history)." Version increments (v1 → v2), the old body is preserved in the version chain (visible via `mnemosyne_recall_canonical(include_history=True)`), and the active body becomes the one the agent sees in recall. The right tool exists; not trying it is the failure.

**Real failure mode (2026-07-06, this user — verbatim correction):** *"why are u not able to subside that entry when i sadi to invalidate it?"* The target was canonical slot id 30 (a 2026-06-27 synthesis pointing at `C:/Users/somew/Documents/hermes-research/...`). The agent tried `mnemosyne_validate(bank="canonical", memory_id=30)` → `bank_invalid`; tried `bank="private"` → `memory_not_found`. The agent concluded "can't be done" and wrote a working-memory note at lower importance saying "the canonical entry 30 is superseded by a 2026-07-06 correction." The next session recalled canonical entry 30 at full strength, saw the working-memory note as lower-priority context, and acted on the stale path. The user called this out explicitly.

**The 2-step fix (canonical supersede):**

```python
# 1. Locate the slot — search the canonical bank, not the regular one
#    The 16-char-hex memory_id from mnemosyne_recall is NOT the canonical-slot ID.
#    Use mnemosyne_recall_canonical(include_history=True) to find the (category, name) pair.
result = mnemosyne_recall_canonical(query="<subject>", include_history=True)
# result.entries: [(category, name, body, version, valid_from, ...), ...]
slot = result.entries[0]  # pick the one that matches

# 2. Write the supersede body to the same slot — version bumps, old body kept as history
mnemosyne_remember_canonical(
    category=slot.category,
    name=slot.name,
    body=(
        "[SUPERSEDED 2026-07-06 by user correction. "
        "Old path: <old path> — INVALID. "
        "Correct: <new path>. "
        "If you need the original content, see version 1 history.] "
        "<new body content, with the corrected fact explicitly stated>"
    ),
    source="user-correction-2026-07-06-supersedes-<old-source>",
)

# 3. Verify version bumped
verify = mnemosyne_recall_canonical(query="<subject>")
assert verify.entries[0].version == 2, "supersede didn't take — re-call with exact (category, name)"
```

**The new body should make the supersede unmissable** — start with `[SUPERSEDED <date> by user correction. Old: ... — INVALID. Correct: ...]` so any future recall consumer (including the agent itself in a later session) sees the supersede marker before reading the rest of the body. Don't bury the correction in a single sentence; the next session might recall the slot, read the body, and miss a small correction inside a long paragraph.

**Asymmetric cost of the antipattern:** leaving stale canon active + adding a working note is a workaround (cheap to write, expensive at next recall — the lower-importance annotation can be missed). Supersede-via-write at the slot is the fix (one extra API call, but the next session's recall correctly returns the new body). When in doubt, do the slot-level fix.

**The antipattern, condensed — what NOT to do:**

- ✗ `mnemosyne_invalidate(memory_id=<canonical-id>)` — wrong bank, returns `memory_not_found`. Entry stays active.
- ✗ `mnemosyne_forget(memory_id=<canonical-id>)` — same problem.
- ✗ `mnemosyne_validate(bank="canonical", memory_id=<id>)` — `validate` only accepts `private` + `surface` per the schema; canonical bank is rejected with `bank_invalid`.
- ✗ Write a working-memory note flagging the canon as stale — the workaround pattern; the next session will likely miss it.
- ✗ Tell the user "I can't invalidate that entry" — try `mnemosyne_remember_canonical` to the same slot FIRST. The right tool exists; not trying it is the failure.
- ✓ `mnemosyne_remember_canonical(category=<cat>, name=<name>, body=<new body>)` to the same slot — the fix. Version bumps, history preserved, recall returns the new body.

## Contradicting canon: trust the newer, then supersede the older

When recall surfaces two canonical entries that disagree (e.g. a 2026-06-24 v2 storage rule at `importance: 0.90` claiming path A, and a 2026-07-06 user correction at `importance: 0.6` claiming path B), the right move is NOT to "pick one and continue." The right move is:

1. **Verify against live state.** `ls`, `read_file`, `terminal` — does path A or path B exist on disk right now? That's the source of truth. Importance scores are not evidence; the filesystem is.
2. **Apply the user-correction-overrides-canon rule** (the 4-state staleness matrix above). User-stated facts beat derived/observed canon, even at lower importance. A 0.6 user-correction always overrides a 0.90 derived rule on the same subject.
3. **Supersede the older entry at the slot** per the section above. The fix is one `mnemosyne_remember_canonical` call to the older slot, not a working-memory workaround and not "I'll be careful to remember which is which."

**Real failure mode (2026-07-06, this host):** the agent correctly identified that a 2026-07-06 user correction overrode a 2026-06-24 v2 storage rule and followed the new path for the task at hand. But it left the 2026-06-24 v2 entry active in the canonical bank. The next session would have recalled the 2026-06-24 rule at full strength (importance 0.90 ≫ 0.6), ignored the working-memory note, and re-introduced the bug. **The agent fixed the symptom, not the cause.** The slot-level supersede is the cause-level fix — and the right tool for it (`mnemosyne_remember_canonical`) was available the entire time the agent was working on the wrong tool.

## The "I tried it, it didn't work, give up" antipattern

The 2-bug failure pattern (in this user) shows up as: agent tries tool A, gets rejection, concludes "can't be done" instead of trying tool B (the documented alternative). The working-memory workaround that follows looks like diligence but is actually a 2-bug: it leaves the underlying problem in place and adds a separate, lower-priority annotation that the next session can miss.

**Rule:** when the first tool returns a rejection for a documented reason (wrong bank, wrong signature, wrong namespace), the right next step is to read the schema / docstring / tool description for the documented alternative — NOT to write a workaround. Three concrete cases from this host:

1. **Canonical supersede:** `mnemosyne_invalidate` returns `bank_invalid` on a canonical-slot ID → use `mnemosyne_remember_canonical` to the same slot.
2. **16-char hex vs integer ID:** `mnemosyne_update` returns `not_found` for an integer canonical-slot ID → use `mnemosyne_remember_canonical` to the same slot (same tool, different ID semantics).
3. **Wrong recall filter:** `mnemosyne_recall(query=..., source="x")` silently no-ops → drop the unsupported kwarg and filter client-side (see "The 2-pass filter rule" above).

The pattern: the tool's rejection is a *signal about the right tool*, not a *terminal answer*. Read the signal, find the right tool, try it. Don't settle for "can't be done."