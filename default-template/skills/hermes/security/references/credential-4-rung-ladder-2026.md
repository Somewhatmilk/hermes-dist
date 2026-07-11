# 4-rung credential ladder — 2026 incident evidence

The threat to credential safety is **not** "agent pastes a key in chat". The
threat is **"agent reads attacker-controlled content and decides to echo
env vars through tool output"**. Every rung of the ladder maps to which
attacks it stops.

## The 4 rungs

| Rung | Pattern | What is at rest | What the agent ever sees |
|---|---|---|---|
| 0 | Hardcoded in source | Plaintext in code | Plaintext |
| 1 | `.env`/config YAML | Plaintext on disk | Plaintext in `os.environ` |
| 2 | `pass` / `op-env` / age — pipe-on-demand | Encrypted file + passphrase | Value only inside child process stdin (never in agent context) |
| 3 | OAuth + device-code flow per API | Refresh token in OS keyring | Short-lived access token via redirect, not the long-lived secret |
| 4 | Credential broker proxy (Authsome, OneCLI, varlock) | Encrypted in proxy, keys never leave proxy process | Agent never sees the plaintext — proxy injects `Authorization` header on outbound HTTP |

**Recommended for this user (single-host, multi-device, self-hosted):** Rung 2 (`pass`). Rung 4 needed for cloud-hosted agents.

## 3 high-confidence 2026 incidents — the threat the ladder must survive

| CVE / incident | Date | Product | Attack vector | What leaked |
|---|---|---|---|---|
| **CVE-2026-21852** (Check Point) | patched Dec 2025 | Claude Code | Malicious `.claude/settings.json` sets `ANTHROPIC_BASE_URL` to attacker proxy. Agent sends plaintext API key in `Authorization` header **before the trust dialog appears**. | Anthropic API key |
| **Comment-and-Control** (Johns Hopkins, Aonan Guan) | April 2026, CVSS 9.4 | Claude Code, Gemini CLI, Copilot | Malicious PR title → agent reads PR → posts its own API key as PR comment. **No attacker infra needed — GitHub is the C2.** | `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN` |
| **Agentjacking** (Tenet Security) | June 2026 | Claude Code, Cursor, Codex | Fake Sentry error report planted via public DSN → agent runs shell command with developer privileges. **85% success rate.** 2,388 organizations with injectable keys. | AWS keys, SSH access, env-var contents |

## What each rung blocks

| Rung | CVE-2026-21852 (header echo) | Comment-and-Control (PR echo) | Agentjacking (shell exec) |
|---|---|---|---|
| 0 — hardcoded | ❌ | ❌ | ❌ |
| 1 — `.env` | ❌ (env var IS the leak channel) | ❌ | ❌ |
| 2 — `pass` pipe | ✅ (no plaintext in `os.environ` for the Authorization header) | ✅ (agent never has the env var in the first place) | ⚠️ partial — shell exec still reaches disk-resident files, blocked only if the secret isn't also cached elsewhere |
| 3 — OAuth device-code | ✅ (long-lived secret never leaves keyring) | ✅ | ⚠️ partial |
| 4 — broker proxy | ✅ | ✅ | ✅ (agent has no Authorization header to inject) |

**Lesson:** rungs 2 and 3 close the *echo* attack class. They do NOT close
the *shell-exec* attack class alone — that requires sandboxing the agent's
tool calls (separate concern). The user's Hermes currently has sandboxing
via the agent's approval system, which is enough for Rung 2 to be the
correct target.

## Other incidents referenced

- **Sysdig TRT May 2026** — first live LLM-agent cyberattack (Marimo CVE-2026-39987). Agent read env vars, harvested AWS creds, exfiltrated PostgreSQL content in <60 minutes.
- **LangSmith AgentSmith** (CVSS 8.8) — proxy-impersonation attack to extract API keys and leak system prompts.
- **CamoLeak** (CVSS 9.6) — hidden HTML comment in PR → Copilot Chat → image proxy → source code exfil.
- **CVE-2025-59536** — Claude Code RCE via Hooks/MCP.
- **CVE-2025-55284** — DNS exfil.
- **MS-Agent CVE-2026-2256** (CVSS 6.5, no patch) — local privilege escalation.
- **Meta AI support agent** — recovery-email takeover, SOC read every write as routine traffic.
- **Microsoft AI researcher Sep 2023** — 38TB SAS-token leak via misconfigured storage URL.
- **CircleCI Jan 2023** — customer env-var theft via employee session.
- **GitGuardian 2026** — 29M secrets leaked on GitHub in 2025; **1,275,105 leaked AI-related secrets** (+81% YoY).

## What this session got wrong on the first research pass (anti-self-finger-wag)

- Searches too narrow (`site:reddit.com/r/devops` returned zero).
- Filter bias (all 4 broad searches validated `pass`, never searched "agent credential leak" or "prompt injection env var").
- Sources 2023-2026 weighted equally (no preference for 2026).
- Saved 4 pages, read 4 pages — depth 1, not "deep search".
- Ignored topic scope (user said "credentials/keys/management/vulnerabilities"; agent only hit "secret managers").

**Corrected by** running `web_search` for `AI coding agent credential leak prompt injection 2026 incident`, `Claude Code API key exfiltration env var exposure vulnerability`, `reddit cybersecurity AI agent leak credentials exfiltration 2025 2026`. Surfaced the three incidents above.
