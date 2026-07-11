# API provider fallback chain — silent, recoverable, agent must check logs

**Status:** CONFIRMED (worked example 2026-07-11)
**Authority:** Live evidence in `~/.hermes/logs/agent.log`

## What the agent should know

When the active model provider goes unreachable, Hermes auto-switches to a fallback provider using a credential pool. **This switch is silent from the agent's perspective** — the conversation continues, the agent sees no error, but its responses may come from a different endpoint with different latency, different style, or different behavior. The fallback chain is:

| Tier | Provider | Notes |
|---|---|---|
| Primary | `provider=minimax` (model `MiniMax-M3`) | Default for default profile |
| Fallback 1 | `provider=custom:yuanyuaicloud.cn` (same model `MiniMax-M3`) | Attached credential pool |
| Fallback 2 | `provider=custom:minnimax.chat` (same model `MiniMax-M3`) | Different endpoint, different creds |

The fallback switches when:
1. Primary provider returns unreachable on health check
2. Repeated `Invalid API response (retry N/3)` warnings exhaust retries
3. The "Provider unreachable — switching to fallback provider..." warning fires (this is the desktop-side surface)

## How to detect a fallback happened

After any session where the user mentions lag, response-quality shift, or "that response felt different," check `~/.hermes/logs/agent.log`:

```bash
# Search for fallback events in the last hour
grep -E "Fallback to|Provider unreachable|Invalid API response \(retry" \
  ~/.hermes/logs/agent.log | tail -20

# Check the desktop.log for user-facing warnings
grep "Provider unreachable" ~/.hermes/logs/desktop.log | tail -20
```

The relevant log lines look like:

```
agent.chat_completion_helpers: Fallback to custom:yuanyuaicloud.cn/MiniMax-M3: attached fallback credential pool
agent.conversation_loop: Invalid API response (retry 1/3): response.content invalid (not a non-empty list) | Provider: model=MiniMax-M3
```

## Worked example (2026-07-11)

This session had **2 fallbacks and 2 retries**:

| Time | Event | From | To |
|---|---|---|---|
| 16:31:13 | Retry 1/3 (same provider, gave up early) | `provider=minimax` | same |
| 17:06:54 | Retry 1/3 (same provider, gave up early) | `provider=minimax` | same |
| 17:09:56 | **Fallback** | `provider=minimax` | `provider=custom:yuanyuaicloud.cn` |
| 17:11:23 | **Fallback** (re-applied) | `provider=minimax` | `provider=custom:yuanyuaicloud.cn` |
| 17:57:21 | **Fallback** (the one during the user's question) | `provider=minimax` | `provider=custom:minnimax.chat` |

The 17:57 fallback was the one I missed. The user's question at 17:57 came in on the new fallback provider, and I was about to claim "no errors I know of" before checking the logs. The actual evidence was in `agent.log` the whole time.

## Why "retries" and "fallbacks" are distinct

| Term | Meaning | Same provider? |
|---|---|---|
| **Retry** | Same call, same model, same provider, just try again. Bounded (3 attempts). | Yes |
| **Fallback** | Different provider entirely. Triggered when primary is unreachable or repeatedly failing. | No |

A retry that succeeds is invisible. A retry that fails at 3/3 may trigger a fallback (or may not, depending on the failure class). The `desktop.log` "Provider unreachable" warning only fires for fallbacks, not retries.

## Rule for the agent

After any session where the user notices a lag or response-quality shift, OR after any session that felt "weird" without explanation, run:

```bash
grep -cE "Fallback to|Provider unreachable|Invalid API response \(retry [0-9]+/3\)" \
  ~/.hermes/logs/agent.log | head -1
```

If non-zero, the session had at least one fallback or retry. Report the count and the timestamp range to the user. **Do not** claim "no errors I know of" without first running this probe.

## What fallback events don't affect

- Working artifacts written to disk (not API-dependent)
- Mnemosyne writes (local SQLite)
- Skill-frontmatter patches (local file)
- Cron jobs (independent process)
- Cua-driver operations (local daemon)

## What fallback events DO affect

- Response latency (different endpoint may be slower)
- Response style (different temperature, different sampling defaults)
- Tool-calling reliability (the new provider may have different JSON-mode behavior)
- Streaming stability (some providers stream more reliably than others)

If a fallback happened mid-conversation and the next response feels different, that may be the cause — not "the agent is being weird."

## Related

- `~/.hermes/logs/agent.log` (authoritative source for fallback events)
- `~/.hermes/logs/desktop.log` (user-facing surface)
- `~/.hermes/logs/errors.log` (tool-execution errors; orthogonal to API fallback)
- `~/.hermes/logs/mcp-stderr.log` (MCP transport errors; orthogonal)
- `~/.hermes/logs/gateway.log` (gateway-side errors; usually the primary source for 503s and connection failures)