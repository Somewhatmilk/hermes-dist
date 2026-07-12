---
name: mnemosyne-memory
description: "Mnemosyne memory subsystem for Hermes Agent — provider wiring, recall discipline, threshold tuning, and dreaming cron. Use when working with mnemosyne store/recall/sleep, debugging memory recall failures, configuring the memory provider, tuning recall precision/recall, or planning a dreaming cron."
version: 2.10.0
author: 'Consolidated 2026-07-02; v2.7.0 2026-07-06 canonical-supersede section (user verbatim correction: why are u not able to subside that entry when i sadi to invalidate it); v2.8.0 2026-07-07 library-vs-wrapper surface distinction + verify-before-cite pitfall (agent cited mnemosyne_graph_link as library function, was wrapper-only); v2.9.0 2026-07-08 3-way memory architecture (Mnemosyne = agent recall, Obsidian = user work surface, Documents/hermes-research = project deliverables) — supersedes the 2026-06-24 "Obsidian as primary short-term memory sink" overclaim; v2.10.0 2026-07-10 data/shared/mnemosyne.db init recipe + profile_isolation auto-create verification (found mid-session: BankManager does NOT pre-create shared surface DB; schema-mirror recipe added; cross-checked vec virtual tables and FTS5 shadow tables).'
author: 'Consolidated 2026-07-02; v2.7.0 2026-07-06 canonical-supersede section (user verbatim correction: why are u not able to subside that entry when i sadi to invalidate it); v2.8.0 2026-07-07 library-vs-wrapper surface distinction + verify-before-cite pitfall (agent cited mnemosyne_graph_link as library function, was wrapper-only); v2.9.0 2026-07-08 3-way memory architecture (Mnemosyne = agent recall, Obsidian = user work surface, Documents/hermes-research = project deliverables) — supersedes the 2026-06-24 "Obsidian as primary short-term memory sink" overclaim.'
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mnemosyne, memory, recall, staleness, dreaming, cron, consolidation, provider]
    category: hermes
    related_skills: [hermes-memory-architecture, session, hermes-misbehavior-diagnosis, hermes-self-improvement, cross-session-rule-audit]
---

# Mnemosyne Memory

> ## Mental Model (read this first)
>
> Mnemosyne is **not a database** in the sense you query with `SELECT * FROM`.
> It is a **note-passing inbox + relevance scorer**. Five things make this
> distinction load-bearing:
>
> 1. **Recall returns *relevant*, not *correct*.** `mnemosyne_recall` ranks
>    memories by importance + recency + similarity. Top-N wins, not "the
>    answer". You still verify the recalled fact against the source before
>    citing it (see `references/verify-before-cite.md`).
> 2. **The four surfaces are NOT interchangeable.**
>    - `mnemosyne_remember` → working memory (importance × veracity, used
>      by recall)
>    - `mnemosyne_remember_canonical` → identity slots (one value per
>      `(category, name)`, supersedes cleanly — for stable "I am X" facts)
>    - `mnemosyne_triple_add` / `_query` → subject-predicate-object graph
>      (for relational facts; traversable via `mnemosyne_graph_*`)
>    - `mnemosyne_scratchpad_*` → ephemeral working notes (session-only,
>      NOT in recall ranking)
>    - `mnemosyne_shared_*` → cross-agent surface (compact, stable meta
>      only — never raw conversation)
> 3. **Memory *layers*, not *types*.** A fact can exist in working (live
>    recall), episodic (consolidated summaries), BEAM tiers (compressed
>    further for hot/cold paths), and graph (relational). You don't
>    pick a layer — the `sleep` cycle moves things between them.
> 4. **Importance + recency + similarity = ranking, not authority.** A
>    high-importance but stale fact will surface; a low-importance but
>    current fact won't. If you need the *authoritative* version, use
>    `mnemosyne_recall_canonical` (returns the single slot value), not
>    `mnemosyne_recall` (returns ranked candidates).
> 5. **It's the agent's notebook, not the user's.** Mnemosyne is what
>    the *agent* recalls next session. For the *user's* browsing
>    surface, see Obsidian (different home, different consumer).
>    See "Memory architecture" below for the 3-way split.
>
> When in doubt: "would I want the agent to recall this next session
> without being told?" → yes → Mnemosyne. "Would I want to look this
> up myself tomorrow?" → yes → Obsidian. "Is it 20KB+ project
> deliverable?" → yes → `Documents/hermes-research/`.
>
> The rest of this skill is the API surface, the recall discipline, the
> dreaming cron, and the gotchas. Read the mental model; skim the rest
> on demand.

Mnemosyne is Hermes's native memory backend (SQLite + sqlite-vec + FTS5, polyphonic recall, Bayesian veracity consolidation). The companion `mnemosyne-hermes` package wires it as a first-class `MemoryProvider`.

**Two surfaces, one DB (NEW 2026-07-07).** This skill previously conflated "Mnemosyne the library" with "Mnemosyne the Hermes wrapper" and got caught. The distinction is load-bearing:

1. **Mnemosyne the library** — `pip install mnemosyne-memory` (PyPI, Abdias J, v3.11.1). Pure Python + SQLite. Public API = 14 lazy exports: `Mnemosyne`, `remember`, `recall`, `get_context`, `get_stats`, `get`, `forget`, `update`, `reclaim_orphans`, `SyncEngine`, `SyncEvent`, `SyncEncryption`, `ConflictResolution`, `run_sync_server`, plus `run_mcp_server` if `mcp` is installed. **No graph, no triple, no invalidate, no validate, no canonical in the library API.** Verified via `import mnemosyne; [a for a in dir(mnemosyne) if not a.startswith('_')]`.
2. **Hermes plugin wrapper** — `~/.hermes/plugins/mnemosyne/__init__.py` (v0.2.0). 19 tool schemas in `tools.py`: the 14 from the library plus `mnemosyne_invalidate`, `mnemosyne_validate`, `mnemosyne_triple_add`, `mnemosyne_triple_query`, `mnemosyne_graph_link`, `mnemosyne_graph_query`, `mnemosyne_remember_canonical`, `mnemosyne_recall_canonical`, `mnemosyne_scratchpad_*`, `mnemosyne_export`, `mnemosyne_import`, `mnemosyne_diagnose`, `mnemosyne_shared_*`. The wrapper is what the agent sees as `mnemosyne_*` tools.

When a tool doc says "available," check whether it's a library symbol or wrapper tool. The DB tables (`graph_edges`, `triples`, `canonical_facts`, `memoria_*`) are written by the wrapper, not the library's `sleep` cycle. Full ground-truth verification recipe → `references/library-vs-wrapper-surface-2026-07-07.md`.

**Memory architecture: where things go (NEW 2026-07-08, user explicit).** Three homes, three consumers, three rules:

1. **Mnemosyne = the agent's recall.** Durable facts, preferences, corrections, importance-scored hybrid search, top-N prefetch on every turn. This is where the agent remembers things across sessions. If a fact will still matter in 7 days, Mnemosyne.
2. **Obsidian vault = the user's personal work surface** (`C:\Users\somew\Desktop\Obsidian Vault\`). The user browses this — projects, slide decks, related work, todo boards, miscellaneous ambitious projects. **The agent may read and write here to help the user track their work, but it is NOT the agent's recall.** The 2026-06-24 description that framed Obsidian as the "primary short-term memory sink" was overclaim; the user's actual framing is "a board I use of some sort." If the user is the primary consumer of the artefact, Obsidian. (See the bundled `note-taking/obsidian` skill — its description carries the corrected framing.)
3. **Project deliverables** → `C:\Users\somew\Documents\hemes-research\<project>\`. Long-form reports, research writeups, full skill plans, the 30KB+ artefacts. Not Mnemosyne (too long, won't surface via recall), not Obsidian (not the user's browsing surface) — a third home for project work.

**Quick decision rule:** "If *the agent* needs to recall it next session → Mnemosyne. If *the user* needs to browse it tomorrow → Obsidian. If it's a 20KB+ project deliverable → `Documents/hermes-research/`." The same fact can live in two homes if both consumers need it (Mnemosyne for the agent to recall, Obsidian for the user to browse — that's the durable-duo pattern, not a violation). What is NEVER a third home: skills (live in `~/.hermes/skills/<category>/<name>/`); Mnemosyne DB rows (live in `~/.hermes/mnemosyne/data/mnemosyne.db`); config (lives in `~/.hermes/config.yaml` + `.env`).

**Three concerns, three homes:**
1. **Setup & wiring** — install, config, integration. *(this file)*
2. **Recall discipline** — when to trust a recalled fact. → `references/recall-discipline.md`
3. **Dreaming cron** — nightly 3-phase consolidation. → `references/dreaming-procedure.md`

---

## Setup

Use `hermes memory setup` / `hermes memory off` — don't hand-edit `config.yaml`. Mnemosyne is selected by setting `memory.provider: mnemosyne`.

**Working config (this host):**

```yaml
memory:
  provider: mnemosyne
  memory_enabled: true
  user_profile_enabled: false
  write_approval: false
  memory_char_limit: 0          # suppress inline RAG block (see Pitfalls)
  user_char_limit: 3000
  flush_min_turns: 999
  nudge_interval: 999
```

Verify with `hermes memory status` — look for `Provider: mnemosyne`, `Plugin: installed ✓`, `Status: available ✓`.

### `.env` (optional, for LLM-backed consolidation)

```
MNEMOSYNE_LLM_ENABLED=true
MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:11434/v1
MNEMOSYNE_LLM_MODEL=qwen2:0.5b
MNEMOSYNE_LLM_API_KEY=ollama
MNEMOSYNE_DATA_DIR=~/.hermes/mnemosyne/data
MNEMOSYNE_AUTO_SLEEP_INTERVAL=20
```

`ollama serve` must be up with `ollama pull qwen2:0.5b`. See `references/sleep-llm-config.md` for why `qwen2:0.5b` and not the bundled GGUF.

## CLI & Python API

```bash
hermes memory status                          # provider health
mnemosyne stats                               # row counts per table
mnemosyne store "fact" source importance      # write (importance 0.0-1.0)
mnemosyne recall "query" 5                    # hybrid search, top 5
mnemosyne forget <id>                         # hard delete
mnemosyne sleep                               # consolidate (needs LLM if enabled)
mnemosyne export backup.json                  # dump
mnemosyne import backup.json                  # restore
```

```python
from mnemosyne import remember, recall
remember("User prefers dark mode", importance=0.9, source="preference")
results = recall("user preferences", top_k=3)
```

**Mnemosyne-CLI vs hermes-CLI:** the agent has `mnemosyne_recall/remember/forget/validate/sleep` tools. The hermes CLI has `hermes mnemosyne inspect/stats/sleep/clear/doctor/export/import`. They're different surfaces — don't conflate.

## Plugin restart / update

```bash
hermes gateway restart                        # after config changes
pip install --upgrade mnemosyne-hermes mnemosyne-memory
hermes gateway restart
```

## Which table to write to (quick decision tree)

Mnemosyne has 5 memory tables. Pick by intent:

| If the fact is about… | Write to |
|---|---|
| System state (your install, config, providers) | `canonical_facts` via `mnemosyne_remember_canonical` |
| A behavior rule the agent must follow | `memoria_instructions` (NOT canonical_facts) |
| A user preference | `memoria_preferences` |
| A session digest / summary | `episodic_memory` (auto via `mnemosyne_sleep`) |
| A persona trait | `memoria_persona` (tier='long_term') |
| A working/plan note (scratch space for the current task) | `scratchpad` (NOT recallable via `mnemosyne recall` — see pitfall below) |

Full schema + decision flow → `references/table-routing.md`.

**The common mistake:** defaulting to `canonical_facts` for everything. Behavioral rules are instructions, not meta-facts. Wrong table = agent sees the rule as historical context and ignores it.

## What to store vs not store

Mnemosyne's design assumes tiered consolidation, not bulk session recall. Store as facts come up; let `mnemosyne sleep` age them.

- **Store:** durable facts (preferences, environment, corrections, lessons). Importance 0.9-1.0.
- **Store low:** transient task state. Importance 0.3-0.6.
- **Don't store:** completed-work logs, PR numbers, single-task state, anything stale in 7 days.
- **Don't bulk-import** past session transcripts — hybrid search makes them queryable without import; importing = noise + duplicates.

## Integration

On each turn, `mnemosyne-hermes` does three things:

1. **Pre-turn prefetch** — injects up to 5 high-relevance memories into context.
2. **Post-turn sync** — writes conversation + decisions to SQLite in the background.
3. **Tool dispatch** — exposes mnemosyne-specific tools (`mnemosyne_recall`, `mnemosyne_remember`, `mnemosyne_sleep`, etc.).

**The agent does NOT always auto-check mnemosyne.** If a topic comes up the prefetch missed, call `mnemosyne recall <topic>` explicitly. Don't assume prefetch covers it.

---

## Pitfalls (index)

Full recipes in the linked references. Skim titles — load the reference only when you hit the failure.

### Setup / install
- **DB at wrong path** — `$HERMES_HOME/mnemosyne/data/mnemosyne.db` is the real DB; `$HERMES_HOME/mnemosyne/mnemosyne.db` is a 0-byte stub from older install. → `references/windows-install-recipe.md`
- **Per-profile isolation is filesystem-level, not column-level (NEW 2026-07-10).** `memory.mnemosyne.profile_isolation: true` does NOT add a `profile_id` column to any table — verified across `working_memory`, `facts`, `memoria_facts`, `consolidated_facts`, `canonical_facts`, `episodic_memory`, `memoria_instructions`, `memoria_preferences`, `memoria_kg`, `memoria_timelines` (none have it). The isolation mechanism is **per-profile SQLite DB files** at `$HERMES_HOME/mnemosyne/data/banks/<sanitized_profile>/mnemosyne.db`, with the default profile served by the main `$HERMES_HOME/mnemosyne/data/mnemosyne.db`. Cross-profile shared memory lives at `$HERMES_HOME/mnemosyne/data/shared/mnemosyne.db` (created via the framework on first share). The hermes_memory_provider's `_resolve_profile_bank()` derives the bank name from `agent_identity` or `HERMES_HOME` basename; `BankManager` creates the directory + DB file on first write. **If `profile_isolation: true` is set but you can't see banks in `data/banks/`, that's correct — they auto-create on first non-default-profile write.** The right validation is to call `MnemosyneMemoryProvider.initialize(session_id, hermes_home=..., agent_identity='communicate-design', profile_isolation=True)` and check that `_profile_isolation_enabled` flips to True. The bank file appears after the first `remember()` call lands.
- **`data/shared/mnemosyne.db` is NOT auto-created on install (NEW 2026-07-10, found mid-session).** The framework's `BankManager` and the default `MnemosyneMemoryProvider.initialize` do NOT pre-create the shared surface DB at `$HERMES_HOME/mnemosyne/data/shared/mnemosyne.db` even when `profile_isolation: true` is set. If `shared_surface_read: true` is enabled in config but `data/shared/` doesn't exist, the first cross-profile shared write will fail. **Symptom:** `FileNotFoundError` or `[Errno 2] No such file or directory: '...data/shared/mnemosyne.db'`. **Fix:** copy the schema from the main DB (no data — just DDL) before any shared-surface writes happen. Verified recipe:
  ```python
  import sqlite3, os
  src = r'C:\Users\<user>\.hermes\mnemosyne\data\mnemosyne.db'
  dst = r'C:\Users\<user>\.hermes\mnemosyne\data\shared\mnemosyne.db'
  os.makedirs(os.path.dirname(dst), exist_ok=True)
  sc = sqlite3.connect(src, timeout=10)
  dc = sqlite3.connect(dst, timeout=10)
  for typ, name, tbl, sql in sc.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL AND type IN ('table','index','view','trigger')").fetchall():
      try: dc.execute(sql)
      except: pass
  dc.commit()
  ```
  The `vec_*` virtual tables will fail to copy (sqlite-vec extension not loaded in your Python session) and `fts_*` shadow tables will be re-created by their parent FTS5 tables. After this, `data/shared/` mirrors the main schema minus vec virtual tables (which auto-materialize on first use). **Right validation:** `os.path.exists('$HERMES_HOME/mnemosyne/data/shared/mnemosyne.db')` and the DB has 50+ tables.
- **`hermes memory status` says "NOT installed"** — that line refers to the optional dashboard plugin, not the provider. Verify with `ls $HERMES_HOME/plugins/mnemosyne/` and `config.yaml: provider: mnemosyne`.
- **Windows: 4 install gotchas** (`HERMES_HOME` env var, `WinError 1314` symlink, plugin-dir-vs-pip-package name collision with eager import, stale GitHub clone). → `references/windows-install-recipe.md`
- **`memory_char_limit=0` does NOT fully suppress the `<memory-context>` block** — verified across multiple turns. Only reliable suppression is `hermes memory off`. Don't claim the knob "fixes" it.
- **The four Mnemosyne surfaces look identical in search (FOUND 2026-07-05 — caught mid-session, user explicitly corrected an "Mnemosyne doesn't have an official repo" claim).** There are FOUR distinct Mnemosyne-named things, easy to conflate: (1) `mnemosyne-memory` on PyPI = the real library (Abdias J); (2) `mnemosyne-hermes` on PyPI = the Hermes wrapper; (3) `~/.hermes/plugins/mnemosyne/` = Hermes bundled plugin (depends on `mnemosyne-memory>=3.1`); (4) `docs.mnemosyne.site` = the docs site (same author). Meanwhile PyPI `mnemosyne` (no suffix) is a 4.4KB dummy by lpalbou, v0.1.0 Mar 2025 — **NOT yours, will install but does nothing.** Always `python -c "import mnemosyne; print(mnemosyne.__version__)"` to verify you're on the real one (expect 3.7.0+). When comparing Mnemosyne with Honcho or any other provider, load the standalone comparison skill → `mnemosyne-vs-honcho` (separate umbrella in `skills/hermes/mnemosyne-vs-honcho/`).

### Recall discipline
- **Recency beats importance on ties** — same-importance facts: the more-recent one wins. The score-weighted ordering can let a stale memory outrank a supersede-statement. → `references/recall-discipline.md`
- **`mnemosyne recall` does NOT search the `scratchpad` table** (FOUND 2026-07-04 reviewing the user's `da151f3644de4eb0` skill-library plan). Scratchpad rows (plan output, working notes, task scratch space) live in their own table — they are NOT indexed in `fts_working` / `fts_facts` / `fts_episodes`. If a user references a "scratchpad id" (short hex like `da151f3644de4eb0`) or asks you to find a plan you wrote earlier, `mnemosyne recall "<id>"` and `mnemosyne recall "<topic keyword>"` both return nothing even when the row exists. **To find a scratchpad row:** query SQLite directly:
  ```bash
  sqlite3 ~/.hermes/mnemosyne/data/mnemosyne.db \
    "SELECT id, substr(content,1,200) FROM scratchpad WHERE id LIKE '%abc123%' OR content LIKE '%keyword%';"
  ```
  **Default rule for any user-cited short hex id:** it is almost certainly a scratchpad id — go straight to the `scratchpad` table, do not waste a recall call.
- **Mnemosyne tables are NOT all `(id, content, …)`** (FOUND 2026-07-04). `memoria_facts` has `(key, value, context_snippet, …)`, `memoria_instructions` has `(key, instruction_text, …)`, `scratchpad` has `content` but is unindexed. Running `SELECT content FROM memoria_facts` returns `OperationalError: no such column: content` and burns a tool call. **Before any `SELECT content FROM <table>` blast, run `PRAGMA table_info(<table>)` first** — full schemas for the four non-obvious tables are in `references/sqlite-direct-inventory.md#schemas-that-dont-have-a-content-column`.
- **Use `temporal_weight` + `temporal_halflife` on `mnemosyne_recall` to demote stale canon (NEW 2026-07-04).** The recall tool's schema accepts these as native parameters — no wrapper needed. Default recall (`temporal_weight=0.0`) ranks by 50% vector + 30% FTS + 20% importance, ignoring time entirely. Setting `temporal_weight=0.4` and `temporal_halflife=96` (hours) demotes 8-day-old entries below today's live corrections without changing the storage schema. Verified live: a 2026-06-30 importance-0.6 `Pattern 7` memory that ranked at the top under default weighting moved to position 5 after temporal weighting, while a today's v4-correction (importance 0.95) moved to position 1. **Rule for any recall that mixes canon with current state:** pass the parameters. Default profile should add `temporal_weight: 0.4, temporal_halflife: 96` as standing defaults to all recall calls that need it; Mnemosyne's preset env vars (`MNEMOSYNE_TEMPORAL_WEIGHT`, `MNEMOSYNE_TEMPORAL_HALFLIFE`) handle the rest. → `references/recall-discipline.md`
- **Verify `memory_id` against `content_preview` before any mutation** — the ID is opaque; the preview is the only handle. 3-step verify (read preview → mutate → re-recall). → `references/recall-discipline.md`
- **Invalidate vs forget vs supersede** — default to `invalidate` (preserves audit). `forget` only when the memory has zero audit value (test data, hallucinations). → `references/recall-discipline.md`
- **`mnemosyne_invalidate` / `mnemosyne_forget` / `mnemosyne_validate` do NOT touch the canonical bank (FOUND 2026-07-06, user explicit correction: "why are u not able to subside that entry when i sadi to invalidate it?").** All three tools operate on `private` and `surface` memory banks only. Canonical entries (the ones written via `mnemosyne_remember_canonical`) live in a separate bank; calling these tools on a canonical-slot ID returns `memory_not_found` or `bank_invalid`, and the entry stays in the canonical bank at full recall strength. **The right way to supersede a canonical entry is to call `mnemosyne_remember_canonical` with the same `(category, name)` slot** — the schema says "a new body supersedes the old one (kept as history)," version bumps v1→v2, the old body is preserved in the version chain, and the next session's recall returns the new body. **The antipattern:** the agent tried `validate`/`invalidate`/`forget` on a canonical ID, got rejection, concluded "can't be done," and wrote a working-memory note at lower importance flagging the canon as stale. The next session recalled the stale canon at full strength and ignored the lower-priority annotation. **Rule:** for canonical supersede, ALWAYS use `mnemosyne_remember_canonical` to the same slot. Don't write working-memory workarounds; don't tell the user "can't be done." The right tool exists; try it before giving up. → `references/recall-discipline.md`
- **2-pass filter rule** — `beam.recall()` accepts only `query/limit/recency_weight/min_importance/include_invalidated`. There is NO `source=`, `domain=`, `tag=`, `time_range=` kwarg. Filter client-side. → `references/recall-discipline.md`
- **Verify before cite any `mnemosyne_*` tool (NEW 2026-07-07, this user).** This skill's CLI & Python API section above lists 8 commands; 5 of them (`store`, `mnemosyne forget <id>`, `mnemosyne export`, `mnemosyne import`, `mnemosyne sleep`) are wrapper tools, not library functions, and 4 of them (`invalidate`, `validate`, `graph_link`, `triple_add`) are wrapper-only and not in the library at all. **The verification recipe before citing a function in chat:**

  ```python
  import mnemosyne
  print(mnemosyne.__version__)        # 3.7.0+ = real (NOT 0.1.0 placeholder)
  print(sorted(a for a in dir(mnemosyne) if not a.startswith("_")))
  # Then check the wrapper for the rest:
  grep -nE "^[A-Z_]+_SCHEMA = \{" ~/.hermes/plugins/mnemosyne/tools.py
  ```

  **Failure mode from 2026-07-07:** agent told user "I can emit `mnemosyne_graph_link` edges" as if it were a Mnemosyne primitive. User asked for verification; agent had to backtrack. **Rule:** if you cannot run the verification in the same turn, say "I'm not certain — let me check" and DO NOT cite the function. The cost of a 5-second `dir(mnemosyne)` check is one tool call; the cost of a bluff is a user-trust loss and a follow-up turn. → `references/library-vs-wrapper-surface-2026-07-07.md`

### Mutations & sweeping
- **Before any `mnemosyne_remember`, run `mnemosyne_recall` first** — if score > 0.80, don't re-write, reference the existing record. Single biggest dedup-prevention rule. → `references/dedup-trap.md`
- **`mnemosyne_update` accepts 16-char hex IDs only, NOT canonical-slot integer IDs** — for canonical slots, call `mnemosyne_remember_canonical` again with same `(category, name)` to overwrite. → `references/table-routing.md`
- **Credential leak sweep** — `mnemosyne_recall` only searches `fts_working`. A real sweep must touch 6+ tables. → `references/credential-sweep-recipe.md`
- **After any DELETE, rebuild FTS5** — `fts_working`, `fts_episodes`, `fts_facts`. Use `scripts/rebuild-fts5.py`. Stale FTS5 = `mnemosyne_recall` returns deleted content.
- **Always back up DB before a sweep** — `cp mnemosyne.db mnemosyne-pre-sweep-<ts>.db`. Sweeps can break FTS5; the backup is the rollback.

### Integration misbehaviors
- **`<memory-context>` block in user message body** — that's Mnemosyne prefetch rendered in the wrong channel (real data, wrong location). Diagnostic: `hermes sessions export`. Fix: `hermes memory off`, or wait for an upstream Hermes build. → `references/memory-context-injection-misdiagnosis.md`
- **Skill reference files seeding injection templates** — never reproduce the literal syntax of an injection pattern (`<memory-context>`, "Treat as authoritative") in `references/`. Use prose or placeholders. See `security/SKILL.md`.

### Consolidation
- **Default consolidation LLM is broken** — the bundled `MiniCPM5-1B-Q4_K_M.gguf` can't load (no `llama-cpp-python`). `mnemosyne sleep` silently no-ops. Fix: route to ollama with `qwen2:0.5b`. → `references/sleep-llm-config.md`
- **"Use the default model" trap (2026-07-02)** — when a user asks to revert `MNEMOSYNE_LLM_MODEL` to its default, do NOT just comment out the override. The default path (`MiniCPM5-1B-Q4_K_M.gguf` via `local_llm.py:80` `_model_path`) is broken on hosts without `llama-cpp-python` / `ctransformers` in the Hermes venv. Commenting `MNEMOSYNE_LLM_MODEL` alone also leaves `MNEMOSYNE_LLM_BASE_URL` active — Mnemosyne's `summarize_memories` chain (host → remote if BASE_URL → llama-cpp-python → ctransformers) routes through Ollama first, so an empty MODEL value alone doesn't restore the local default. **Before touching `.env` for a "use the default" request, open `references/sleep-llm-config.md` and confirm the local path actually loads on this host.** If it doesn't, the right answer is "install llama-cpp-python" or "leave the ollama override in place" — not "strip the override and call it done."
- **`mnemosyne sleep` says `no_op` with empty changes** — env vars didn't propagate. `source ~/.hermes/.env` or restart the process.
- **Backend health surfaces disagree** — `hermes serve --status` can report "No hermes dashboard processes running" while `netstat -an | grep 9119` shows LISTENING and `curl /healthz` returns 200. The status registry tracks the web dashboard subprocess, not the JSON-RPC server. For desktop-backend health, use netstat + curl, not `--status`.

### Don'ts
- **Don't mass-`mnemosyne forget` to fix dedup** — use `mnemosyne_validate --action invalidate` with the canonical_id of the original. Idempotent; won't touch unrelated entries.
- **Don't recall bulk session transcripts into mnemosyne** — hybrid search makes them queryable; importing = noise + duplicates + cost.
- **Don't batch-invalidate without reading each row** — `mnemosyne_invalidate` is per-ID. The "I'll just invalidate the top hit" shortcut often nukes the wrong row.
- **Don't re-state the stale fact in chat before invalidating** — the reply is logged; restating keeps the stale string in recall. Phrase corrections as "the latest fact says X; the older Y is invalidated."
- **Don't trust importance over recency** — importance is "how much should this matter," not "is this still true."
- **DON'T replay the full 24h transcript at session start (NEW 2026-07-06, user explicit correction).** The correct cross-session context bridge has four layers, ranked by selectivity: (1) Mnemosyne canonical slots (`mnemosyne_remember_canonical`) — identity, voice, dispatch, preferences — always injected, no recall cost; (2) Mnemosyne top-N hybrid recall (`mnemosyne_recall` with `temporal_weight=0.4, temporal_halflife=96`) per turn — ~500 tokens, 90% of the value; (3) on-demand `session_search(session_id=X)` or `mnemosyne_recall(query=...)` when the user references prior context — zero cost until triggered; (4) `mnemosyne_sleep` nightly consolidation that turns working notes → episodic summaries → memoria triples. **Full transcript replay causes 8 measured failures** — token cost (5-15K extra per turn for a 24h session), lost-in-the-middle attention, prompt-cache invalidation (kills the prefix-cache hit rate), context pollution (old corrections bleed into new questions), voice drift (assistant sounds like yesterday's, not optimal for today), prefill latency (0.3-0.8s per 5K tokens), scope creep (old work invades new tasks), and information decay (most of the 24h isn't relevant to the current question). **Rule of thumb:** if the user asks "where did we leave X", the answer is `session_search(query="X", sort=newest, limit=3)` to find the most recent 1-3 relevant sessions, not "load the last 24h and grep." Full transcripts stay queryable on demand via `session_search` — no need to pre-inject them. Full reasoning, alternatives considered, and the worked top-5 session-start prompt: `references/cross-session-context-bridge.md`.

---

## Reference Files

### Setup & wiring
- **[references/windows-install-recipe.md](references/windows-install-recipe.md)** — full Windows install with 4 gotchas (HERMES_HOME env var, WinError 1314 symlink workaround via robocopy, plugin-dir name collision + line-31 eager-import patch, stale GitHub clone cleanup).
- **[references/sleep-llm-config.md](references/sleep-llm-config.md)** — why the bundled GGUF is broken, how to route consolidation to ollama with `qwen2:0.5b`, model head-to-head benchmark, verification recipe.
- **[references/table-routing.md](references/table-routing.md)** — full 5-table routing matrix (canonical_facts / memoria_instructions / memoria_preferences / memoria_persona / episodic_memory), decision flow, `memoria_instructions` schema, integer-ID vs 16-char-hex update API.
- **[references/cross-session-context-bridge.md](references/cross-session-context-bridge.md)** (NEW 2026-07-06) — why "replay the last 24h" is the wrong context-bridge mechanism; the 4-layer replacement (canonical slots → top-N recall → on-demand session_search → sleep consolidation); the 8 measured failure modes; the worked session-start prompt that injects top-5 memories + last 1-3 relevant session snippets without bulk-loading transcripts. User verbatim correction: *"i never asked for it to be reloaded in full, that would defeat the purpose... top 5 with temporal weighting... if more is needed then session_search the relevant session."*

### Recall & discipline
- **[references/library-vs-wrapper-surface-2026-07-07.md](references/library-vs-wrapper-surface-2026-07-07.md)** (NEW 2026-07-07) — verified ground truth distinguishing the 14-symbol Mnemosyne library API from the 19-tool Hermes wrapper; the `graph_edges` / `triples` DB tables; verification recipe; failure case from this session. **Read this before citing any `mnemosyne_*` function in chat.**
- **[references/recall-discipline.md](references/recall-discipline.md)** — 4-state staleness matrix, recency-as-tie-breaker, 4-action decision tree (invalidate / forget / supersede / verify), pre-action verification protocol, 2-pass filter rule, "verify SDK signature before planning against it."
- **[references/dedup-trap.md](references/dedup-trap.md)** — the 9-vs-237 dedup failure mode, fingerprint audit recipe, write-then-forget anti-pattern, the "recall before remember" rule.
- **[references/threshold-tuning-recipe.md](references/threshold-tuning-recipe.md)** — the 4-knob matrix (`vec_weight` / `fts_weight` / `importance_weight` / `temporal_weight`) tuned for an always-recording agent. **CRITICAL 2026-07-05 fix**: the four weight knobs in `config.yaml: memory.mnemosyne` are **DEAD CODE** — Mnemosyne reads env vars only (`MNEMOSYNE_VEC_WEIGHT`, etc.). The recipe now lives in `.env`, with config.yaml holding only the non-weight knobs (`auto_sleep`, `sleep_threshold`, `fact_recall_enabled`, `prefetch_content_chars`, `profile_isolation`). Includes the live verification recipe (env-var check vs config.yaml read) so users can confirm the tuning actually took effect. User-applied 2026-07-05; synthesized from dev.to "We Tried 6 Memory Providers" + Mnemosyne config docs.

### Sweeping & safety
- **[references/credential-sweep-recipe.md](references/credential-sweep-recipe.md)** — full 6-table sweep recipe (found 33 plaintext leaks), `[REDACTED-...]` marker convention, decision matrix after sweep, rotation follow-up.
- **[references/memory-context-injection-misdiagnosis.md](references/memory-context-injection-misdiagnosis.md)** — diagnostic for the `<memory-context>`-in-user-body bug, 6 hypotheses ruled out, the `hermes sessions export` proving step, "what to do while bug is unfixed."
- **[references/sqlite-direct-inventory.md](references/sqlite-direct-inventory.md)** — when the CLI isn't enough: row counts, schema inspection (`PRAGMA table_info` for non-`content` tables: `memoria_facts`/`memoria_instructions`/`scratchpad`), fingerprint dedup, hard-delete vs invalidate.

### Dreaming
- **[references/dreaming-procedure.md](references/dreaming-procedure.md)** — full Light/Deep/REM 3-phase procedure, 4-dimension scoring (novelty/durability/specificity/reduction), 60% MEMORY.md capacity guardrail, REM approval-gated by default, cron schedule, 50-write cap, verification checklist.

### Scripts
- **[scripts/mnemosyne-credential-sweep.py](scripts/mnemosyne-credential-sweep.py)** — re-runnable cross-table credential sweep. Customize PATTERNS, run, get per-(table, column, row_id, excerpt) report.
- **[scripts/rebuild-fts5.py](scripts/rebuild-fts5.py)** — rebuild `fts_working`, `fts_episodes`, `fts_facts` after any DELETE. Required because FTS5 rowid→content mapping doesn't auto-sync.

---

## Cross-references

- `mnemosyne-vs-honcho` — the standalone comparison skill (loaded when user asks "should I add Honcho?" or "Mnemosyne vs Honcho"). Verifies the four Mnemosyne-named surfaces and the architecture decision matrix.
- `hermes-memory-architecture` — session-start hooks and the "I forget between sessions" framework. Its v1.1.0 update adds the explicit "Cross-session context bridge" section (4-layer mechanism, selectivity ladder) that the pre_llm_call hook implements; the Mnemosyne-specific recall mechanics live in this skill.
- `hermes-misbehavior-diagnosis` — when the agent is using wrong memories, the first move is reading live state, not memory.
- `session` — broader persistence-stack setup (config, profiles, state). Owns the "what stays where across the dual-dir Windows home" rule.
- `cross-session-rule-audit` — finding which rules in memory are violated and why.
- `hermes-self-improvement` — when to promote a memory pattern into a skill.
