# hermes-changelog.py — Cross-Session Change Log

## What it does

Writes a timestamped entry to **two surfaces** at once:

1. **Obsidian vault** (human-browsable audit log):
   `~/Desktop/Obsidian Vault/Hermes Engine/changes/<ISO-timestamp>-<slug>.md`

2. **Mnemosyne shared surface** (agent-readable cross-session sync):
   `~/.hermes/mnemosyne/data/shared/mnemosyne.db` (via `working_memory` INSERT,
   importance=0.8, scope=global, veracity=stated)

Other agents with `shared_surface_read: true` will see these writes in their next recall. This is the practical cross-session "synced brain" mechanism — not real-time, but eventual-consistency at session-boundary granularity.

## Install

```bash
mkdir -p ~/.hermes/scripts
# Copy hermes-changelog.py from the dist repo:
cp default-template/scripts/hermes-changelog.py ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/hermes-changelog.py
```

## Enable shared-surface reads

In `~/.hermes/config.yaml` under `memory.mnemosyne`:

```yaml
mnemosyne:
  shared_surface_read: true        # recall merges shared-surface results
  shared_surface_path: data/shared/mnemosyne.db
```

Restart hermes gateway: `hermes gateway restart`

## Usage

```bash
# Log a skill ship
python3 ~/.hermes/scripts/hermes-changelog.py \
  --kind skill-shipped \
  --slug cross-session-todo-handoff \
  --summary "New opt-in skill for cross-session todo continuity" \
  --details "Writes a work.in_progress canonical slot + dated mnemosyne_remember. Survives context consolidation."

# Log an architecture shift
python3 ~/.hermes/scripts/hermes-changelog.py \
  --kind architecture-shift \
  --slug ollama-to-llama-swap \
  --summary "Removed Ollama, switched to llama-swap" \
  --details "MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:8089/v1. 3 models served: qwen3-8b, qwen2.5-3b, qwen2.5-14b."

# Read recent changes
python3 ~/.hermes/scripts/hermes-changelog.py --list

# Obsidian-only mode (skip Mnemosyne write)
python3 ~/.hermes/scripts/hermes-changelog.py --no-mnemosyne --kind ... --slug ... --summary ... --details ...
```

## Kinds

| Kind | When to use |
|---|---|
| `skill-shipped` | A new skill is added to default-template/ |
| `skill-modified` | A skill is updated (size, content, or version bump) |
| `architecture-shift` | A config or wiring change that affects the system shape |
| `config-change` | A specific config value changed (model, port, etc.) |
| `memory-update` | An important fact was added to Mnemosyne |
| `tool-installed` | A new tool / script / hook was added |
| `bug-fix` | A bug was fixed |
| `other` | Anything else (default to 'other' if unsure) |

## When to call it

- After committing a new skill or major skill change
- After modifying config.yaml in default-template/
- After enabling/disabling a container (firecrawl, searxng, camofox, llama-swap)
- After switching local LLM provider or model
- After any architectural decision worth knowing about later

## When NOT to call it

- For routine bug fixes that don't change behavior across sessions
- For ephemeral state (current task, current model's output)
- For things already in the canonical slot `work.in_progress` (those go in Mnemosyne via `mnemosyne_remember_canonical`)

## Related skills

- `cross-session-todo-handoff` — companion skill for the canonical-slot pattern
- `mnemosyne-tuning` — recall-weight tuning; with `shared_surface_read: true` and importance ≥0.8, your cross-session writes surface reliably
- `kanban-worker-lifecycle` — if you want a long-running kanban worker to mirror Mnemosyne writes back to Obsidian on a schedule (not required; the script writes both directly)

## Filesystem layout

```
~/.hermes/scripts/
  hermes-changelog.py            # this tool
~/Desktop/Obsidian Vault/
  Hermes Engine/
    changes/                     # auto-created; one .md per logged change
      2026-07-12T08-49-20-hermes-changelog-v1.md
      2026-07-12T08-48-57-ollama-to-llama-swap.md
      ...
~/.hermes/mnemosyne/data/shared/
  mnemosyne.db                   # shared-surface DB; one row per change
```

## Verification

After running the tool:

```bash
# Obsidian
ls -la ~/Desktop/Obsidian\ Vault/Hermes\ Engine/changes/

# Mnemosyne shared DB
sqlite3 ~/.hermes/mnemosyne/data/shared/mnemosyne.db \
  "SELECT id, content, source, timestamp FROM working_memory ORDER BY timestamp DESC LIMIT 5"

# From another session: should now appear in recall
python3 -c "from hermes_agent.plugins.mnemosyne import recall; print(recall('recent changes', top_k=5))"
```