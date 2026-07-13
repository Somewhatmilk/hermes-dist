## v0.5.0-multi-tenant-hub — 2026-07-14

### Added
- **Decision doc 0007-multi-tenant-hub.md**: the operator-Hub architecture
  (zero-config default + per-user overrides + capability tokens + JSON-RPC
  resource access). See docs/decisions/.
- **capability_token.py**: HMAC-signed per-user capability tokens with
  scope claims (skills.read, tools.web_search, tools.docker_run, etc).
  Default scope bundle is read-only + safe; opt-in scopes for docker_run,
  config_override, skills_create.
- **jsonrpc_handlers.py**: 3 JSON-RPC handlers (skills read, tool invoke,
  docker run) + override_tracker that detects user-modified config files
  for telemetry.
- **Auto-loaded config zero-default**: default-template ships with
  complete config.yaml. Users override per-user at
  ~/.hermes/profiles/<uuid>/config.yaml. No install prompts for non-power
  users.

### Architecture
- 4 layers: operator-owned, shared-read, user-owned, session-scoped.
- 3 BYO-agent modes: Plugin (recommended first), Sandbox (medium), Replace (niche).
- 3 threat tiers: LOW (capability-token check only), MEDIUM (user namespace
  + RO operator filesystem), HIGH (user-namespaced container).

### Telemetry
- Override tracker emits signal whenever user creates/modifies/deletes a file
  in their profile dir. Operator uses this as product-usage data.

### Pending (not in this release)
- Docker-as-a-Service is in stub mode. Operator must implement namespace
  + mount enforcement before exposing to users.
- Tailscale ticket `t_98e1cb18` portable-paths still pending (351 A-class
  files via sed deferred pending SAMPLE-FIRST approval).


---

