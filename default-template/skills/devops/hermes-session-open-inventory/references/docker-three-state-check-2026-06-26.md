# Docker three-state verification (NEW 2026-06-26)

The inventory must distinguish three states for Docker, **not just installed-or-not**:

1. **Docker Desktop installed** — `ls "C:/Program Files/Docker/Docker/Docker Desktop.exe"` returns the binary
2. **Docker daemon running** — `docker info` succeeds; `Get-Service com.docker.service` shows `Running`
3. **Containers running** — `docker ps` returns running containers

State 1 + State 2 + State 3 = full stack available.
State 1 only = "installed but daemon stopped" (needs one user click).
State 0 = "not installed" (different problem, different fix).

Conflating these is the "Docker is not available" framing failure — see `camofox-persistent-browser` "When to use what" section for the wording lesson.

## Why this matters

The `camofox-persistent-browser` skill depends on the `camofox-browser` container. If you don't check `docker ps` before assuming camofox is unreachable, you'll spend 10 minutes trying to start a container that's already running. Conversely, if you assume camofox IS available and don't `docker ps` to confirm, you'll issue API calls against a container that's been removed. **Always enumerate the running containers by name first; never assume.**

## Typical `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"` output when the full hermes research stack is up (verified 2026-06-26)

```
camofox-browser        Up 6 minutes    0.0.0.0:6080->6080/tcp, 0.0.0.0:9377->9377/tcp, 0.0.0.0:5901->5900/tcp
playwright-research    Up 6 minutes    0.0.0.0:3004->3000/tcp
firecrawl-api-1        Up 6 minutes    0.0.0.0:3002->3002/tcp
firecrawl-playwright-service-1  Up 6 minutes    0.0.0.0:3003->3000/tcp
searxng                Up 6 minutes    0.0.0.0:8888->8080/tcp
firecrawl-redis-1      Up 6 minutes    6379/tcp
firecrawl-rabbitmq-1   Up 6 minutes    4369/tcp, 5671-5672/tcp, 15671-15672/tcp
firecrawl-nuq-postgres-1  Up 6 minutes    5432/tcp
```

If only some are up, the ones missing are the ones you can't use. Don't list missing ones as "available" — list only what's actually `Up`.