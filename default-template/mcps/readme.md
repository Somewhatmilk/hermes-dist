# mcps/ — starter compose-yaml templates for common MCP-server containers

This directory ships starter Docker Compose templates for MCP servers
you might want to host for your hermes-dist users. These are **starting
points**, not production-ready — review the bind mounts, ports, and
image tags before deploying.

## What's here

- `filesystem-mcp.yml` — `@modelcontextprotocol/server-filesystem`, gives
  agents scoped read/write to a host directory
- `browser-worker.yml` — generic Playwright/headless browser MCP
- `web-search.yml` — SearXNG instance for privacy-respecting web search
- `readme.md` — this file

## How to use

```bash
# Pick a template
cp mcps/filesystem-mcp.yml /opt/mcp/filesystem-mcp/docker-compose.yml

# Edit the bind-mount paths to match your environment
# (the defaults are placeholders — DO NOT run as-is)

# Bring it up
cd /opt/mcp/filesystem-mcp && docker compose up -d

# Verify
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep mcp
curl -fsS http://127.0.0.1:<port>/health
```

## Network exposure model (per hermes-dist design)

By default, all MCP containers bind to `127.0.0.1:<port>` (loopback
only). To make them reachable from your Tailscale tailnet (so other
users' hermes agents can hit them), bind to the Tailscale IP:

```yaml
ports:
  - "100.106.125.105:8082:8082"   # Tailscale-only bind
```

Do NOT bind to `0.0.0.0` — that exposes the MCP to your LAN, which
defeats hermes-dist's Tailscale-isolation design.

## Authentication (recommended)

For non-loopback binds, the MCPs should authenticate. The shipped
templates use API key auth via the `MCP_API_KEY` env var; generate one
with `openssl rand -hex 32` and pass it to users via your out-of-band
channel (not via email, not via the relay).

## Updating

These are starting points. Real-world MCP server configuration is
operational — pick a template, fork it, customize it for your stack.
The dist repo's role is to make the FIRST 30 SECONDS of "I want to
host an MCP server" easy, not to provide turnkey production infra.

## What you should NOT do

- Don't bind any MCP to `0.0.0.0` without authentication
- Don't use the default `MCP_API_KEY` from these templates
- Don't run as root in the container (the templates use `1000:1000`)
- Don't bind-mount `/` or any directory that contains secrets
- Don't expose filesystem-mcp's full /opt/mcp/scratch without scoping
