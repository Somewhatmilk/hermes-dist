# Verified Paths and Entry Points (2026-06-26)

The 5 write-targets and 6 verified entry points on this Windows host, with the
exact paths and invocation patterns verified live. This is the knowledge bank
that `verify_tool_installed.py` scans and reports against.

**Caveat:** "verified" means "verified on 2026-06-26." Path and tool state
change over time. Run `verify_tool_installed.py --all` at session start to
re-verify.

---

## The 5 verified write-targets

The agent most commonly reads from or writes to 5 filesystem roots. Every
install verification should scan all 5 (sibling dirs are the common miss).

### 1. Hermes home (canonical user state)

```
C:\Users\somew\AppData\Local\hermes\
```

**Contains:**
- `default/` — default profile state, `skills/`, `logs/`
- `skills/` — **cross-profile shared skills** (auto-loaded by default profile). Contains ~31 categories.
- `profiles/<name>/` — per-profile state. Current profiles: `communicate-design`, `default`, `model-merger`, `prompt-engineering`, `sandbox`, `software-engineering`
- `hermes-agent/` — Hermes app source (upstream)
- `hermes-agent-self-evolution/` — **GEPA repo** (DSPy + GEPA optimizer, pip-installed)
- `mnemosyne/` — Mnemosyne DB (`data/mnemosyne.db`)
- `plugins/`, `cron/`, `cache/`, `logs/`, `state.db`, `state-snapshots/`, `gateway/`

**Read-only (for me):** `hermes-agent/` (upstream), `state.db`, `mnemosyne/data/*.db`.
**Writable:** `skills/`, `profiles/<name>/skills/`, `cache/`, `logs/`.

### 1a. Cross-profile shared skills (`hermes/skills/`)

The canonical location for skills that should be visible across all profiles.
Auto-loaded by the `default` profile.

```
C:\Users\somew\AppData\Local\hermes\skills\<category>\<skill-name>\SKILL.md
```

Current categories (verified 2026-06-26): `apple`, `autonomous-ai-agents`, `camofox-black-screen-fix`, `comfyui-workflow-api`, `creative`, `data-science`, `deep-research-methodology`, `devops`, `dogfood`, `email`, `firecrawl-endpoints-v2`, `github`, `hermes`, `hermes-config-cli-gotchas`, `hermes-redaction-bypass`, `media`, `meta`, `mlops`, `note-taking`, `productivity`, `routing`, `research`, `self-hosted-services`, `smart-home`, `social-media`, `software-development`, `windows-task-scheduler-bash`, `yuanbao`, plus `.curator_backups/` and `.hub/`.

### 1b. Per-profile skills (`hermes/profiles/<name>/skills/`)

Per-profile overrides or skills that should only be visible inside one profile.
Not auto-loaded by other profiles. **Cross-profile writes need explicit
confirmation.**

```
C:\Users\somew\AppData\Local\hermes\profiles\<profile-name>\skills\<category>\<skill-name>\SKILL.md
```

Example: `prompt-evolve-loop` lives at `profiles/prompt-engineering/skills/software-development/prompt-evolve-loop/SKILL.md` and is only visible inside the `prompt-engineering` profile.

### 2. Hermes research (long-term research, OCD workflow)

```
C:\Users\somew\Documents\hermes-research\
```

Currently contains only `ocd-projects/hermes-analysis/`. This is where the user
moved OCD work in 2026-06-24 v5 (per memory). Use this for long-term research
notes, reports, and skill/reference mirrors.

### 2a. OCD project root

```
C:\Users\somew\Documents\hermes-research\ocd-projects\hermes-analysis\
```

Mirrors some skills and research from the legacy `One-Cut-Deeper` clone.

### 3. OCD clone (legacy, OLD primary home)

```
C:\Users\somew\Downloads\One-Cut-Deeper\
```

Still has the legacy layout (`bin/`, `camofox-docker/`, `hermes-hooks/`,
`hermes-scripts/`, `notes/`, `plans/`, `playwright-research/`, `profiles/`,
`projects/`, `research/`). Superseded by `hermes-research/` for active work
but kept for backward compatibility.

### 4. Hermes agent venv site-packages

```
C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\
```

Where `evolution` is pip-installed (editable, via `__editable__.hermes_agent_self_evolution-0.1.0.pth`). Where DSPy, GEPA-standalone, and most Python deps live. Read-only for the agent (don't write directly — use `pip install` from the venv's python).

### 5. Mnemosyne private bank (default profile)

```
C:\Users\somew\AppData\Local\hermes\default\memories\
```

The default profile's Mnemosyne private bank. Read via `mnemosyne_recall`,
write via `mnemosyne_remember`. **Don't edit files in this dir directly** — go through the Mnemosyne API or `hermes memory` CLI.

---

## The 6 verified entry points

### 1. `hermes` CLI

**Path:** `C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes`

**Verified invocation:** `hermes --version` → `Hermes Agent v0.17.0 (2026.6.19) · upstream 1abfa66b`

**Subcommands (verified):** `chat`, `model`, `fallback`, `secrets`, `migrate`, `gateway`, `proxy`, `lsp`, `setup`, `postinstall`, `whatsapp`, `slack`, `send`, `login`, `logout`, `auth`, `status`, `cron`, `webhook`, `portal`, `kanban`, `hooks`, `doctor`, `security`, `dump`, `debug`, `backup`, `checkpoints`, `import`, `config`, `pairing`, `skills`, `bundles`, `plugins`, `mnemosyne`, `photon`, `curator`, `memory`, `tools`, `computer-use`, `mcp`, `sessions`, `insights`, `claw`, `version`, `update`, `uninstall`, `acp`, `profile`, `completion`, `dashboard`, `desktop`, `gui`, `logs`, `prompt-size`.

**NOT a subcommand:** `evolution`, `evolution.skills.evolve_skill`. These will fail with `error: argument command: invalid choice`.

### 2. `python` (hermes agent venv)

**Path:** `C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`

**Verified invocation:** `python -c "import sys; print(sys.version)"` → `3.11.x`

**Use this for:** any `python -m <package>` invocation that needs the venv's site-packages.

### 3. `python -m evolution.skills.evolve_skill` (GEPA)

**Module path:** `C:\Users\somew\AppData\Local\hermes\hermes-agent-self-evolution\evolution\skills\evolve_skill.py`

**Verified invocation:**

```bash
"$HERMES_HOME/hermes-agent/venv/Scripts/python.exe" -m evolution.skills.evolve_skill --help
```

**Returns:** click usage block listing all options:

```
--skill TEXT                    Name of the skill to evolve [required]
--iterations INTEGER            Number of GEPA iterations [default: 10]
--eval-source [synthetic|golden|sessiondb]
--dataset-path TEXT             Path to existing eval dataset (JSONL)
--optimizer-model TEXT          Model for GEPA reflections [default: openai/gpt-4.1]
--eval-model TEXT               Model for evaluations [default: openai/gpt-4.1-mini]
--api-key TEXT                  API key (literal). If omitted, uses --api-key-env.
--api-key-env TEXT              Env var name to read API key from (e.g. MINIMAX_API_KEY).
--base-url TEXT                 API base URL (literal). If omitted, uses --base-url-env.
--base-url-env TEXT             Env var name to read base URL from (e.g. MINIMAX_BASE_URL).
--hermes-repo TEXT              Path to hermes-agent repo
--run-tests                     Run full pytest suite as constraint gate
--dry-run                       Validate setup without running optimization
```

**CRITICAL L6 gotcha:** pass `--hermes-repo "$HERMES_HOME"`, NOT `--hermes-repo "$HERMES_HOME/hermes-agent"`. Default scans the bundled repo's `skills/` directory (upstream), not user-written skills.

### 4. Mnemosyne

**CLI subcommand:** `hermes mnemosyne <verb>`

**Verified invocation:** `hermes mnemosyne --help` → usage block listing subcommands.

**DB location:** `C:\Users\somew\AppData\Local\hermes\mnemosyne\data\mnemosyne.db` (+ `-shm` and `-wal` for SQLite WAL mode).

### 5. DSPy

**Module path:** `C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\dspy\`

**Verified:** 20+ files matched in site-packages, including `dspy/teleprompt/gepa/gepa.py` (DSPy's built-in GEPA integration).

### 6. GEPA standalone

**Module path:** `C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\gepa\gepa_utils.py`

**Verified:** 1 file matched at the canonical standalone location.

---

## Cost / time budget for the verification scan

`verify_tool_installed.py --all` runs in **~12 seconds** end-to-end on this host (verified 2026-06-26). Cost is negligible compared to the cost of shipping a skill on the wrong premise (~30+ minutes of downstream work + a trust-budget hit).

**Budget guidance:**

- **At session start:** always run `--all` (12 sec). Output the report.
- **Before writing any skill whose prerequisite is a tool:** run `--tool <name> --strict` (5-10 sec). If exit 1, stop and diagnose.
- **Before answering "is X installed?":** run `--tool <name>` (5-10 sec). Quote the report, not the memory row.
- **Every 5-10 turns during long sessions:** re-run `--all` if the session has touched installs, venv rebuilds, or repo moves. Cheap to run, expensive to skip.

---

## Cross-reference

- `scripts/verify_tool_installed.py` — the utility that produces these reports.
- `references/inventory-misuse-incidents.md` — the GEPA "we ran this yesterday" incident that drove this knowledge bank.
- `self-evolution-install-2026-06-25.md` (in `hermes/skills/meta/hermes-self-improvement/references/`) — the canonical install recipe for GEPA, including the L6 `--hermes-repo` gotcha in full detail. This file is a condensed cross-reference; read the original for full install procedure.