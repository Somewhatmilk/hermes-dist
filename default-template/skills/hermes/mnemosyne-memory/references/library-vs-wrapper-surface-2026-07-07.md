# Library vs Wrapper surface — verified ground truth (2026-07-07)

The Mnemosyne skill text in `mnemosyne-memory/SKILL.md` previously listed `mnemosyne` CLI commands and Python imports without distinguishing between the upstream library API and the Hermes plugin wrapper. On 2026-07-07 this caused the agent to cite `mnemosyne_graph_link` as if it were a library function, and the user had to ask for verification. This file is the verified ground truth so the next session doesn't repeat the failure.

## The two surfaces

### Surface A: Mnemosyne the library

- PyPI: `mnemosyne-memory` (NOT the bare `mnemosyne` package, which is a 4.4 KB placeholder)
- Author: Abdias J
- License: MIT
- Version: 3.11.1 (verified 2026-07-07 on this host)
- Source: `~/.hermes/hermes-agent/venv/Lib/site-packages/mnemosyne/__init__.py`

**Public API (14 lazy exports + 1 conditional):**

| Symbol | Module | Purpose |
|---|---|---|
| `Mnemosyne` | `.core.memory` | Main class |
| `remember` | `.core.memory` | Write |
| `recall` | `.core.memory` | Hybrid search |
| `get_context` | `.core.memory` | Build context block |
| `get_stats` | `.core.memory` | Row counts |
| `get` | `.core.memory` | Get by ID |
| `forget` | `.core.memory` | Hard delete |
| `update` | `.core.memory` | Update content/importance |
| `reclaim_orphans` | `.core.memory` | Cleanup |
| `SyncEngine` | `.core.sync` | Cross-device sync |
| `SyncEvent` | `.core.sync` | Sync event class |
| `SyncEncryption` | `.core.sync` | E2E encryption |
| `ConflictResolution` | `.core.sync` | Sync conflict strategy |
| `run_sync_server` | `.core.sync_server` | Server mode |
| `run_mcp_server` | `.mcp_server` | Only if `mcp` is installed |

**NOT in the library:** `invalidate`, `validate`, `triple_add`, `triple_query`, `graph_link`, `graph_query`, `remember_canonical`, `recall_canonical`, `scratchpad_*`, `export`, `import`, `diagnose`, `shared_*`. None of these are Mnemosyne library functions.

### Surface B: Hermes plugin wrapper

- Path: `~/.hermes/plugins/mnemosyne/`
- Source: `__init__.py` (1914 lines) + `tools.py` (tool schemas, 569 lines)
- Schemas registered: 19 (`mnemosyne_remember`, `mnemosyne_recall`, `mnemosyne_shared_remember`, `mnemosyne_shared_recall`, `mnemosyne_shared_forget`, `mnemosyne_shared_stats`, `mnemosyne_sleep`, `mnemosyne_stats`, `mnemosyne_invalidate`, `mnemosyne_validate`, `mnemosyne_get`, `mnemosyne_triple_add`, `mnemosyne_triple_query`, `mnemosyne_remember_canonical`, `mnemosyne_recall_canonical`, `mnemosyne_scratchpad_*`, `mnemosyne_export`, `mnemosyne_update`, `mnemosyne_forget`, `mnemosyne_import`, `mnemosyne_diagnose`, `mnemosyne_graph_query`, `mnemosyne_graph_link`)
- Handler implementations live in `__init__.py:_handle_*` methods; the `graph_link` handler is at line 1683, `triple_add` at 1415, `graph_query` at 1658.

## The DB tables (the bridge between surfaces)

55 tables in `~/.hermes/mnemosyne/data/mnemosyne.db`. The wrapper writes to all of them; the library writes to a subset. Notable ones:

- `graph_edges` — 1,060 rows on this host, all `edge_type='ctx'`, written by an older `gists`/`facts` path that is no longer active in the current `sleep` cycle. **No relation extraction runs in current `mnemosyne_sleep`.**
- `triples` — 6 rows on this host, all from manual `mnemosyne_triple_add` calls. Examples: `(user, owns website, ...)`, `(gpg-keypair-2026-07-05, fingerprint, 51EC...)`.
- `canonical_facts` — versioned canon slots, written by `mnemosyne_remember_canonical`.
- `memoria_*` — preferences, instructions, persona, kg, timelines.
- `working_memory` / `episodic_memory` / `facts` — the BEAM tiers.

## Verification recipe (use before any citation)

```python
# 1. Verify the library you think is loaded
import mnemosyne
print(mnemosyne.__version__)                # 3.7.0+ = real; 0.1.0 = placeholder
print(sorted(a for a in dir(mnemosyne) if not a.startswith("_")))
# ^ this is the full library API; if your function isn't in this list,
#   it's wrapper-side

# 2. Verify the wrapper is wired
import os
WRAPPER = os.path.expanduser("~/.hermes/plugins/mnemosyne")
print(os.path.exists(WRAPPER + "/tools.py"))  # True
# Then grep for the schema:
import subprocess
r = subprocess.run(
    ["grep", "-nE", "^[A-Z_]+_SCHEMA = \\{", WRAPPER + "/tools.py"],
    capture_output=True, text=True
)
print(r.stdout)
# If your function is in the schema list, it's wrapper-side.

# 3. Verify the DB schema (when in doubt about persistence)
import sqlite3
conn = sqlite3.connect(os.path.expanduser("~/.hermes/mnemosyne/data/mnemosyne.db"))
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print([r[0] for r in cur.fetchall()])
```

## Failure case (2026-07-07, this user)

Sequence:

1. User asked about merging relations between memories after review/validation.
2. Agent (without verifying) cited `mnemosyne_graph_link` as a "Mnemosyne primitive" in the curator pipeline.
3. User asked: "is `mnemosyne_graph_link` part of mnemosyne or u just going to create it? since we lack a knowledge graph..."
4. Agent ran the verification above. Found: not a library function; is a wrapper tool at `__init__.py:1683`. Backed off the citation.
5. Right answer all along: the wrapper has the tool, the library does not. The DB has the table. The relation can be written, but the agent's claim was wrong about where the function comes from.

## Rule for next session

Before telling the user "I can use X" or "X is available," run the verification in the same turn. If you cannot, say so explicitly and offer to check. **Never bluff on a function name.**

Cost of the verify-before-cite check: 1 `terminal` call, ~2 seconds, ~30 tokens of output.
Cost of the bluff: user trust loss, follow-up turn, "agent made it up" memory entry.
