---
name: 503-fallback-chain-diagnostic
description: How to diagnose 503 errors and fallback-chain failures in Hermes. Use when the user reports agent stops mid-turn, "continue" appears with no prior context, or asks "is the fallback model messing up my context?". Verified 2026-07-09 with this user's actual agent.log.
---

# 503 + Fallback-chain diagnostic (this user)

## The user-facing symptom

- Agent stops responding mid-turn
- A bare "continue" message arrives as a new user message
- The user is unsure whether to retype the question or wait
- The agent, when it does respond, "feels like" it lost prior reasoning

## What is actually happening (verified 2026-07-09, this user's `~/.hermes/logs/agent.log`)

```
[primary provider returns HTTP 503]
  └─ error: 抱歉，当前服务暂时繁忙，已尝试多个渠道均未成功 (the proxy yuanyuaicloud.cn
              tried all its upstream channels, all busy)
  └─ Hermes retries same provider 3× with backoff (2.4s, 4.4s, ...)
  └─ All 3 retries 503
  └─ [Hermes activates fallback chain]
  └─ info: Fallback activated: MiniMax-M3 → MiniMax-M3 (minimax)
  └─ [fallback provider returns HTTP 401]
  └─ error: login fail: Please carry the API
  └─ [no more fallbacks configured → request fails]
  └─ [the gateway injects "continue" as a recovery prompt to keep the
     session alive while waiting for primary to recover]
```

**The "continue" is NOT the fallback model loading with bad context.** The
fallback model never loads. It 401s on auth. What you see is the gateway
asking the primary provider to retry — and "continue" is the literal
placeholder it injects when the original request can't be reconstructed.

## The diagnostic — read the logs, not the symptoms

```bash
# Primary log file (newest first, ~1-2MB)
ls -lt ~/.hermes/logs/ | head -5

# Search for the actual chain
grep -nE '503|Fallback activated|MINIMAX_API_KEY|exhausted|all_retries_failed' \
  ~/.hermes/logs/agent.log | tail -30

# Also errors.log has the retry-with-backoff trace
grep -nE '503|Retrying API call' ~/.hermes/logs/errors.log | tail -20
```

The 3 lines that tell you what's broken:

| Log line | What it means |
|---|---|
| `Streaming failed before delivery: Error code: 503 - all_retries_failed` | **Primary provider is the problem.** Proxy upstream is busy. Wait or switch primary. |
| `Fallback activated: <primary> → <fallback>` | Fallback chain is being attempted. Good — the gateway is doing its job. |
| `credential pool: marking <PROVIDER>_API_KEY exhausted (status=401)` | **Fallback credential is bad.** The fallback can never load. Either rotate the key or remove the dead fallback from config. |

## Fixing the chain — three options, in priority order

### Option 1: Fix the fallback credential (cheapest, biggest impact)

```bash
# Find which env var holds the bad key
grep -nE 'minimax|MINIMAX|api_key' ~/.hermes/config.yaml ~/.hermes/.env
# Update it (use hermes-redaction-bypass skill if pasting the literal value)
# Then restart the TUI to reload
```

A working fallback means a 503 from the primary is non-fatal — the user
sees a brief delay, not a "continue" prompt.

### Option 2: Add a tertiary fallback

```yaml
# ~/.hermes/config.yaml
fallback_providers:
  - provider: minimax
    model: MiniMax-M3
  - provider: openrouter     # new — cheaper, different infra
    model: anthropic/claude-3-haiku
```

### Option 3: Switch primary off the busy proxy

```yaml
# ~/.hermes/config.yaml
model:
  default: MiniMax-M3
  provider: minimax          # was: custom:yuanyuaicloud.cn
  base_url: https://api.minimax.io/anthropic
```

Eliminates 503s entirely if the proxy is the bottleneck. Downside: you
lose the proxy's price-aggregation benefit (if any).

## When to NOT chase 503s

If the user is on a critical long-running task and the 503 only happens
on one turn out of twenty, the 1-2s fallback delay is acceptable. Don't
chase stability at the cost of complexity unless 503s are a real
productivity hit. The decision threshold: if the user has to retype
their question more than once a week because of "continue" prompts,
the chain is broken and needs fixing.

## Cross-references

- Main skill: `hermes-misbehavior-diagnosis` (changelog v2.7.0 added
  "i had to send a new input for you to continue" as a trigger phrase)
- Related: `hermes-config-cli-gotchas/references/pass-resolver-cold-start-test.md`
  (when the 401 is a pass-pointer issue, not a primary 503)
- Related: `~/.hermes/docs/secret-store-patterns.md` (pass / gpg /
  bitwarden chain architecture, relevant to fixing the 401)
