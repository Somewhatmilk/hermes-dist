# 0007 — Multi-Tenant Hub Architecture

> **Status:** Accepted · **Date:** 2026-07-14 · **Author:** Operator

## Context

The operator runs Hermes locally on a single PC. Users connect directly over
Tailscale and use the local instance as-is. By default the install works
without any user config — `default-template/` ships a complete, working profile.
Users only touch config when they want to override behaviour, ship their own
agent, or add hooks. Modifications are a telemetry signal that informs operator
roadmap.

Three competing constraints:

1. **Zero-friction install** — `curl | bash` should produce a working agent.
2. **Resource sharing** — users should be able to leverage the operator's hard-
   won skills, tools, and Docker services.
3. **Isolation** — user A must not break user B, nor the operator's instance.

## Decision

Adopt the **Hermes Hub** pattern: operator runs a single multi-tenant Hermes
instance. Users connect via Tailscale + HMAC capability token.

### Layers (top-down)

| Layer | Owner | Examples |
|---|---|---|
| 0 — operator | operator | hermes-dist repo, relay, default-template, Docker services |
| 1 — shared read | operator + user (RO) | skills, tools via JSON-RPC, Docker via DaaS |
| 2 — user owned | user | profile config, scripts, BYO agent, scratch, kanban, mnemosyne-private |
| 3 — session scoped | user (ephemeral) | session state, sandbox overflow, in-flight calls |

### Resource access

| Resource | Mechanism |
|---|---|
| Skills | RO filesystem mount OR `GET /api/v1/skills/<name>` |
| Tools | `POST /api/v1/tools/invoke` with capability token scopes |
| Docker | `POST /api/v1/docker/run` runs in user-namespaced container |

### BYO-agent modes

1. **Plugin** (recommended first) — user's module hooks into operator's runtime
2. **Sandbox** (medium) — user's agent runs in user-namespaced subprocess
3. **Replace** (niche) — user ships entire agent runtime

### Threat tiers

| Tier | Action | Sandbox |
|---|---|---|
| LOW | operator-side execution | capability token check only |
| MEDIUM | writes to user scratch | user namespace, operator FS is RO |
| HIGH | docker run, full agent | user-namespaced container + audit |

## Consequences

* Operator must issue capability tokens per user (HMAC-signed).
* Relay exposes 3 new JSON-RPC endpoints; telemetry surface tracks overrides.
* `default-template/` ships zero-config; per-user overrides live under
  `~/.hermes/profiles/<uuid>/`.
* Docker-as-a-Service requires Linux user namespace support; macOS/Windows
  use WSL2/Docker Desktop equivalents.

## Rollback

If multi-tenant proves too complex, fall back to per-user hermes installs
(each user has their own operator-side hermes with no shared infra).
