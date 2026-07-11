# .env Stock-vs-Custom Classification + Load-Bearing Audit — 2026-07-03

Companion to `hermes-this-host-layout-2026-07-01.md`. That reference
documents **what's on disk**; this one documents **how to tell what's
custom vs upstream, and which custom keys actually do anything**.

## Why this is needed

A user's `~/.hermes/.env` is a mix of:
- **Stock keys** (also in `hermes-agent/.env.example`) — leave at upstream defaults, re-documentation is noise
- **Custom keys** (added by user, fork, or skill) — these need an INSTALL.md "addon" appendix so a fresh-machine install knows what to bring
- **Custom keys that aren't actually read** — dead config that looks important but doesn't affect runtime

Telling the three apart requires three separate checks:

1. **Stock detection** — diff active keys against upstream `.env.example`
2. **Load-bearing classification** — tag each custom key as MANDATORY / OPTIONAL / DISABLED by reading actual code/skills/config for env-var consumers
3. **Disabled-but-preserved** — grep for commented-out keys with `# disabled YYYY-MM-DD: <reason>` annotations; these are gold, do not delete

## Stock detection — the technique

A naive `grep '^KEY='` misses upstream keys because the upstream
`.env.example` ships keys as **commented-out templates** (`# OPENROUTER_API_KEY=*** so the grep must accept both shapes.

```bash
# Stock keys in upstream .env.example (extracts both active and commented)
grep -oE '^[#[:space:]]+[A-Z][A-Z0-9_]+=' "$HERMES_HOME/hermes-agent/.env.example" \
  | sed -E 's/^#[[:space:]]+([A-Z_][A-Z0-9_]*)=.*/\1/' | sort -u > /tmp/stock.txt

grep -E '^[A-Z_][A-Z0-9_]*=' "$HERMES_HOME/hermes-agent/.env.example" \
  | sed -E 's/^([A-Z_][A-Z0-9_]*)=.*/\1/' | sort -u >> /tmp/stock.txt
sort -u /tmp/stock.txt -o /tmp/stock.txt

# Active keys in user's .env (skip comment lines)
grep -vE '^\s*#' "$HERMES_HOME/.env" \
  | grep -E '^[A-Z_][A-Z0-9_]*=' \
  | sed -E 's/^([A-Z_][A-Z0-9_]*)=.*/\1/' | sort -u > /tmp/yours.txt

# Truly custom = in yours, NOT in upstream
comm -23 /tmp/yours.txt /tmp/stock.txt
```

For the live session on 2026-07-03, the active `.env` had 29 keys;
**18 stock, 11 custom**.

### Stock keys (kept at upstream defaults — do not re-document)

```
BROWSER_INACTIVITY_TIMEOUT, BROWSER_SESSION_TIMEOUT,
BROWSERBASE_ADVANCED_STEALTH, BROWSERBASE_PROXIES,
CAMOFOX_URL, FIRECRAWL_API_KEY, GATEWAY_ALLOW_ALL_USERS,
IMAGE_TOOLS_DEBUG, MINIMAX_API_KEY, MOA_TOOLS_DEBUG,
OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN, TERMINAL_ENV,
TERMINAL_LIFETIME_SECONDS, TERMINAL_MODAL_IMAGE,
TERMINAL_TIMEOUT, VISION_TOOLS_DEBUG, WEB_TOOLS_DEBUG
```

### Custom keys (require addon documentation)

```
API_SERVER_KEY, CIVITAI_API_KEY, CUSTOM_PROVIDER_YUANYUAICLOUD_CN_KEY,
DISCORD_BOT_TOKEN, FIRECRAWL_API_URL, HERMES_SPOTIFY_CLIENT_ID,
MNEMOSYNE_FORCE_LOCAL, MNEMOSYNE_HOME, MNEMOSYNE_LLM_API_KEY,
MNEMOSYNE_LLM_ENABLED, OBSIDIAN_VAULT_PATH
```

## Load-bearing classification

Stock vs custom is not the only axis. A custom key may be:
- **MANDATORY** — install fails or is severely degraded without it
- **OPTIONAL** — improves functionality, not required
- **REDUNDANT** — the secret also lives elsewhere (e.g. `config.yaml` `api_key:` field) so the env var is a parallel duplicate
- **DEAD** — no code, skill, or config reads it; can be deleted
- **DISABLED** — commented out with a `# disabled YYYY-MM-DD:` reason; preserve

### How to verify "actually read"

Three searches, in order of speed. Each is constrained to avoid the
full-recursive-grep timeouts on large `hermes-agent/` trees:

```bash
# Tier 1 — fast: only the skills and plugins dirs
grep -rlE "MNEMOSYNE_LLM_API_KEY|MNEMOSYNE_LLM_ENABLED" \
  "$HERMES_HOME/skills" "$HERMES_HOME/plugins" 2>/dev/null

# Tier 2 — targeted code: the hermes-cli entry points only
grep -E "MNEMOSYNE_LLM_API_KEY|MNEMOSYNE_LLM_ENABLED" \
  "$HERMES_HOME/hermes-agent/hermes_cli/config.py" 2>/dev/null

# Tier 3 — if you must recurse, restrict by file extension and timeout
timeout 10 grep -rE "OBSIDIAN_VAULT_PATH" \
  "$HERMES_HOME" --include="*.py" --include="*.md" --include="*.yaml" 2>/dev/null
```

For the live session:
- `MNEMOSYNE_LLM_API_KEY` / `MNEMOSYNE_LLM_ENABLED` / `MNEMOSYNE_FORCE_LOCAL` — **DEAD**. The Mnemosyne plugin reads `MNEMOSYNE_HOST_LLM_ENABLED` and `MNEMOSYNE_LLM_BASE_URL` (different env-var names). The three custom keys are personal-preference documentation, not load-bearing.
- `OBSIDIAN_VAULT_PATH` — only consumed by the `note-taking/obsidian` skill and one in-passing reference in `research/llm-wiki`. OPTIONAL.
- `CIVITAI_API_KEY` — only consumed by the `model-merger` profile's research skill. OPTIONAL for everyone except that profile.
- `CUSTOM_PROVIDER_YUANYUAICLOUD_CN_KEY` — **REDUNDANT**. `config.yaml` `custom_providers[0].api_key` already holds the same value. Becomes MANDATORY only if user refactors the secret out of YAML.
- `MINIMAX_API_KEY` — MANDATORY: `config.yaml` `model.fallback_providers` lists it first; without it the agent loses its primary fallback when the default provider is rate-limited.
- `MNEMOSYNE_HOME` — MANDATORY on relocated installs (when `HERMES_HOME` isn't `~/.hermes`), OPTIONAL on default installs (plugin falls back to `~/.hermes/mnemosyne`).
- `HERMES_HOME` itself — set inside the user's `.env` as a self-reference (`HERMES_HOME = C:\Users\somew\.hermes`). Python's `dotenv` accepts spaces around `=` so this parses fine, but the value is **host-specific** (Class B from the `.env` portability memory).

### Custom-provider env-var naming convention

Custom providers without an explicit `key_env` field default to env-var
name `CUSTOM_PROVIDER_<NAME>_KEY` (uppercased, non-alphanumerics →
underscore). This is hermes-cli's fallback (see
`hermes_cli/config.py`). If you add a `custom_providers` entry with
`name: Yuanyuaicloud.cn`, the env-var is
`CUSTOM_PROVIDER_YUANYUAICLOUD_CN_KEY`. Verifiable with:

```bash
grep -B1 -A12 "_CUSTOM_PROVIDER_LIKE_FIELDS\|default.*key_env\|key_env.*default" \
  "$HERMES_HOME/hermes-agent/hermes_cli/config.py" 2>/dev/null
```

## Disabled-but-preserved keys

Two commented-out keys in the user's `.env` carry gold:

```ini
#MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:11434/v1   # disabled 2026-07-02: use local MiniCPM5-1B-Q4_K_M.gguf default
#MNEMOSYNE_LLM_MODEL=qwen2:0.5b                     # disabled 2026-07-02: revert to default local MiniCPM5-1B-Q4_K_M.gguf can be used if u want to use a local model instead.
```

**Rules for these:**

1. **Preserve inline.** The next maintainer needs the `disabled YYYY-MM-DD: <reason>` comment to know whether to re-enable.
2. **Add to the addon doc, not the .env.** INSTALL.md should have a "Disabled (preserved inline)" section that quotes these so a fresh install knows they exist.
3. **Do NOT uncomment without checking first.** Re-enabling changes runtime behavior (consolidation now talks to a local LLM endpoint that may or may not be running).

## Output format — addon doc skeleton

For each custom key, the addon reference doc should record:

```
### <KEY_NAME>
- **Class:** Secret | Host-specific | Toggle | Partial-secret
- **Mandatory / Optional / Disabled:** <one>
- **Why:** <one sentence connecting the key to config.yaml or a skill>
- **Where it's read:** <grep result, e.g. "skills/note-taking/obsidian/SKILL.md only">
- **Format notes:** <e.g. "single-quote if path contains a space">
- **See also:** <related skill or upstream doc>
```

Skeleton produced 2026-07-03 at `Downloads/env-addons.md` (6.9 KB).

## Pitfalls

1. **Spaces around `=` are valid in Python `dotenv`.** Don't "fix"
   `HERMES_HOME = C:\Users\somew\.hermes` to `HERMES_HOME=*** — it
   works as-is, and rewriting changes mtime/blame without changing
   behavior.
2. **Recursive grep on `$HERMES_HOME/hermes-agent/` will time out** (180s+)
   on a full source tree. Always restrict to `hermes_cli/`, `agent/`,
   or by extension (`--include="*.py"`). Tier 1 (skills + plugins
   only) is the right starting point.
3. **A key can be stock in `.env.example` AND in `auth.json` at the
   same time** (Discord token, Spotify client_id). The two surfaces
   serve different purposes: `.env` is loaded by dotenv, `auth.json`
   is loaded by the platform-accounts skill. Don't try to unify them.
4. **Don't classify by name alone.** `MNEMOSYNE_LLM_API_KEY` *looks*
   like a Mnemosyne plugin key, but the plugin actually reads
   `MNEMOSYNE_LLM_BASE_URL`. Always grep before tagging.
5. **The 5 per-profile `.env` files** (md5 `0d724557394a7bd93bb484414d084268`)
   are byte-identical duplicates of global — see
   `hermes-this-host-layout-2026-07-01.md` § "The duplicate-`.env` trap".
   The custom-vs-stock classification should be done on the global
   `.env`; per-profile copies are an existing problem to clean up
   separately, not part of this audit.