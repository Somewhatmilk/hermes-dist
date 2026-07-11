# Verified Hermes-on-This-Host Layout — 2026-07-01

Live-verified filesystem facts about the actual install at `C:\Users\somew\AppData\Local\hermes\` on this Windows host. Captured during a session where the user asked about hermes config layout, MCP, and SOUL.md layering. Each fact was verified by reading the actual file (path, size, line count, md5 where relevant) — not from memory or framework docs.

## Top-level layout

```
C:\Users\somew\AppData\Local\hermes\   ← HERMES_HOME (env var confirmed)
├── config.yaml          18,488 B / 707 lines   (global, the merge base)
├── .env                 25,113 B / 31 entries  (cross-cutting secrets)
├── SOUL.md              2,171 B / 34 lines     (THE identity file — only one)
├── hermes-agent\                                 (source checkout, read-only at runtime)
├── hermes-agent-self-evolution\                  (GEPA repo, pip-installed)
├── default\  communicate-design\  model-merger\  adversary\  reviewer\  software-engineering\
├── skills\                                    (31 global skills, always loaded)
├── plugins\                                   (2: mnemosyne, session-router)
├── gateway\  desktop\  cron\  kanban\         (shared infra)
├── mnemosyne\data\mnemosyne.db                (private bank, ~29 MB)
├── logs\  cache\  audio_cache\  browser_screenshots\  ...
└── auth\  auth.json
```

Stale directories that DO NOT need to exist:
- `C:\Users\somew\.hermes\` — empty stray from an earlier install. Only contains `cache/` and a stub `mnemosyne/`. Safe to `rm -rf`.
- `C:\Users\somew\.mnemosyne\` — Mnemosyne legacy location. Live DB is now at `HERMES_HOME\mnemosyne\data\mnemosyne.db`. Shared bank at `.mnemosyne\data\shared\mnemosyne.db`. Consolidate via `MNEMOSYNE_HOME` env var in `.env`.

## SOUL.md layering — verified behavior

| File | Loaded as identity? | When |
|---|---|---|
| `HERMES_HOME/SOUL.md` | **YES — slot #1 of system prompt** | Every session, every profile |
| `profiles/<name>/SOUL.md` | **NO** — context/markdown only | Read by profile loader as notes |
| `hermes-agent/docker/SOUL.md` | **NO** | Source-tree file, only used as fallback seed when `HERMES_HOME/SOUL.md` is empty/missing |
| `/personality <name>` (slash command) | Session-level overlay | Built-in (concise, technical, pirate, …) or custom via `agent.personalities.<name>` in config.yaml |

**Implication:** to change identity, edit `HERMES_HOME/SOUL.md`. The 6 per-profile `SOUL.md` files (one per profile) are NOT personality overrides — they may shape context but not identity. If a profile has a `SOUL.md` that looks like a duplicate of the global (as `default/SOUL.md` does), it can be deleted without runtime impact.

## Config merge semantics — verified

At profile launch, Hermes does a deep merge:
1. Load `HERMES_HOME/config.yaml` (base layer)
2. Load `profiles/<active>/config.yaml` (overlay)
3. Keys in overlay override base; absent keys inherit

**Critical gotcha:** `hermes config set KEY VAL` writes to the ACTIVE PROFILE's `config.yaml`, NOT the global. There is no CLI flag to set a key globally. To set global keys, edit `HERMES_HOME/config.yaml` directly.

## Verified state — profile files (this host, 2026-07-01)

| Profile | `config.yaml` | `.env` | `SOUL.md` | `skills/` count | Notes |
|---|---|---|---|---|---|
| `default` | 3,326 B ✅ | ❌ MISSING | 2,258 B (duplicate of global + 1 line) | 1 (just `devops/` stub) | Coordinator placeholder; OK as-is |
| `communicate-design` | 610 B ✅ | 24,825 B | ✅ | 32 | |
| `model-merger` | 16,179 B ✅ | 24,825 B | ✅ | 20 | |
| `retrospect` → `adversary` | **MISSING** | 24,825 B | ✅ | 17 | **WILL CRASH** — needs `config.yaml` |
| `reviewer` | **❌ MISSING** | 24,825 B | ✅ | 17 | **WILL CRASH** — needs `config.yaml` |
| `software-engineering` | 3,521 B ✅ | 24,825 B | ✅ | 17 | |

**The duplicate-`.env` trap:** all 5 per-profile `.env` files are byte-identical (md5 `0d724557394a7bd93bb484414d084268`). They differ from the global `.env` by only 2 lines (`CIVITAI_API_KEY` value + a comment). This is a maintenance liability, not a feature. Fix: per-profile `.env` should ONLY contain profile-specific secrets; global `.env` holds cross-cutting secrets; most profiles should have NO `.env` file (inherit from global).

**Fix for the 2 missing `config.yaml` files:**
```bash
head -8 /c/Users/somew/AppData\Local\hermes\profiles\model-merger/config.yaml \
  > /c/Users\somew\AppData\Local\hermes\profiles\retrospect/config.yaml
head -8 /c/Users\somew\AppData\Local\hermes\profiles\model-merger/config.yaml \
  > /c/Users\somew\AppData\Local\hermes\profiles\reviewer/config.yaml
```

## Mnemosyne DB paths — verified

- **Private bank:** `C:\Users\somew\AppData\Local\hermes\mnemosyne\data\mnemosyne.db` (~29 MB, active writes)
- **Private stub (do not use):** `C:\Users\somew\AppData\Local\hermes\mnemosyne\mnemosyne.db.empty-stub-2026-06-27` (0 bytes)
- **Shared surface:** `C:\Users\somew\.mnemosyne\data\shared\mnemosyne.db` (~942 KB)

If you write Mnemosyne rows directly, target the `…\mnemosyne\data\mnemosyne.db` path — the empty-stub file is a historical artifact and not the live DB.

## Global skills inventory — 31 entries

```
HERMES_HOME/skills/
├── apple
├── autonomous-ai-agents/         (4 sub-skills: claude-code, codex, opencode, hermes-agent)
├── camofox-black-screen-fix
├── comfyui-workflow-api
├── computer-use
├── creative/                      (14+ sub-skills)
├── data-science/                  (jupyter-live-kernel)
├── deep-research-methodology
├── devops/                        (16+ sub-skills)
├── dogfood
├── email/                         (himalaya)
├── firecrawl-endpoints-v2
├── github/                        (6 sub-skills)
├── hermes/                        (5 sub-skills)
├── hermes-config-cli-gotchas
├── hermes-redaction-bypass
├── image-processing/
├── media/                         (gif-search, songsee, youtube, heartmula)
├── meta/                          (cartographer, dreaming, hermes-self-improvement)
├── mlops/                         (10+ sub-skills)
├── note-taking/                   (obsidian)
├── productivity/                  (15+ sub-skills)
├── routing
├── prompt-engineering/
├── research/                      (10+ sub-skills)
├── self-hosted-services/
├── smart-home/                    (openhue)
├── social-media/
├── software-development/          (16+ sub-skills)
├── windows-task-scheduler-bash
└── yuanbao
```

**The "specialization" question:** because every profile inherits all 31 global skills, per-profile `skills/` directories ADD on top — they don't subtract. True specialization requires either moving skills out of global into per-profile folders OR using `hermes skills config` to disable per-profile (runtime filter, no file moves).

## Common paths that get confused — the cheat sheet

| Concept | Real path | Common wrong guess |
|---|---|---|
| Identity SOUL.md | `HERMES_HOME/SOUL.md` | `profiles/default/SOUL.md` (no override power) |
| Mnemosyne private DB | `HERMES_HOME/mnemosyne/data/mnemosyne.db` | `HERMES_HOME/mnemosyne/mnemosyne.db` (0-byte stub) |
| Kanban DBs (per-board) | `HERMES_HOME/kanban/boards/<board>/kanban.db` | `HERMES_HOME/kanban.db` (top-level, not what dispatcher reads) |
| Hermes CLI binary | `HERMES_HOME/hermes-agent/venv/Scripts/hermes` | `~/.local/bin/hermes` (symlink) |
| Ollama (local) | `http://127.0.0.1:11434/v1` | Various |
| llama-swap (alternative) | `http://127.0.0.1:8089/v1` | Often confused with Ollama |