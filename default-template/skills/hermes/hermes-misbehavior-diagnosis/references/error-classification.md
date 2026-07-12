## Pre-flight procedure (run before heavy LLM turns)

```bash
# For each provider in the pool, hit its /v1/models with a 2s timeout
for provider in custom:yuanyuaicloud.cn minimax openrouter ollama ollama-cloud opencode-zen; do
  case $provider in
    custom:*) base_url="https://yuanyuaicloud.cn/v1" ; key="$CUSTOM_PROVIDER_YUANYUAICLOUD_CN_KEY" ;;
    minimax)  base_url="https://api.minimax.chat/v1" ; key="$MINIMAX_API_KEY" ;;
    openrouter) base_url="https://openrouter.ai/api/v1" ; key="$OPENROUTER_API_KEY" ;;
    ollama)   base_url="http://127.0.0.1:11434/v1" ; key="ollama" ;;
    # ... add yours
  esac
  http_code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $key" \
    "$base_url/models")
  echo "$provider → HTTP $http_code"
done
```

**Decision rule:** route the heavy call to the first provider returning 2xx. If none work, **fail fast with a clear error** — don't try and hope.


## Error classification table

| Error class | What it means | Action | Example |
|---|---|---|---|
| `CONNECTION_ERROR` / `Connection refused` | TCP layer failed: host not listening, DNS, RST, bind issue | **Fix the bind/network, not retry.** Add to OLLAMA_HOST=0.0.0.0 or check firewall. | Ollama on `[::1]` only — IPv4 clients get refused. |
| `TIMEOUT` / `RequestTimeout` | Server up, just slow (cold load, GC, rate-limit queue, network) | **Gap + retry with backoff.** Cold local LLM load = 5-10s first call. | First Ollama inference after idle 5min+ timeout. |
| `429` / `RATE_LIMIT_EXCEEDED` | Explicit backpressure | **Honor Retry-After header.** Exponential backoff. | Provider hitting per-minute quota. |
| `503` / `SERVICE_UNAVAILABLE` | Server overloaded | **Gap + retry, fewer concurrent calls.** | Provider rolling restart. |
| `401` / `INVALID_API_KEY` | Auth | **Don't retry. Fix the key.** Check which env var the pool is actually using. | `MINIMAX_API_KEY` is invalid; the pool silently fell back to a different provider. |
| `401` with literal `pass:api/...` string in the X-Api-Key header (NEW 2026-07-07, this user) | The `.env` file uses `KEY=pass:api/X` pointers and the `pass` vault resolver (`agent/secret_sources/pass_source.py`) didn't run / didn't resolve them in the current process. The credential pool then stores the literal `pass:api/X` string as the access_token and sends it to the provider. **Same root cause hits every consumer of the same env var at once** — `pass:api/telegram-bot` rejected by Telegram, `pass:api/discord-bot` rejected by Discord, `pass:api/minimax` 401 on minimax, all in the same minute. The visible signature in logs: `pass: resolved 0/7 entries` (resolver ran but found no values) OR the resolver never appeared in the log at all (resolver didn't run in this process). | **Two-step diagnostic — never patch `.env` first.** (1) Run the resolver standalone in a fresh Python process: `cd ~/.hermes/hermes-agent && PYTHONPATH=. ./venv/Scripts/python.exe -m agent.secret_sources.pass_source ~/.hermes/.env`. **Expected output:** `applied: 7 (…MINIMAX_API_KEY…, …OPENROUTER_API_KEY…); skipped: 1; warnings: 0`. If you get `applied: 0/7` and the `pass` binary is on PATH (`shutil.which('pass')` returns a path), the resolver itself is broken. (2) If step 1 returns `applied: 7`, the resolver works in isolation — the bug is **env-var inheritance from a parent process that never resolved**. The Electron desktop main process is a Node.js process that doesn't import `hermes_cli.env_loader`; it reads `.env` via JS dotenv, gets the literal `pass:api/...` strings, and `spawn()`s the Python gateway child. Python inherits the parent's `os.environ` with literals already set. The fix is `hermes gateway restart` so the spawned child process runs the patched resolver from a clean slate. **Anti-pattern:** editing `.env` to hardcode resolved values. That bypasses the resolver and creates two secret-management paths; the right fix is process-restart of the affected child. Cross-reference: the Windows path-mangling fix in `pass_source.py:_fetch_one` that converts `C:\\\\...` to `/c/...` at the call site is documented in `hermes-windows-filesystem-ops` philosophy #11. | `agent.log`: `pass: resolved 0/7 entries in 282ms` immediately followed by `Error code: 401 … 'X-Api-Key' field of the request header`. Same minute, `errors.log`: `[Telegram] Failed to connect … The token 'pass:api/telegram-bot' was rejected`. Multiple consumers fail in lockstep because they share the same broken env-var inheritance. |
| `403` / `PERMISSION_DENIED` | Auth ok, scope wrong | **Don't retry. Fix the request or upgrade plan.** | |
| `500` / `502` | Server-side bug | **Check provider status page. Single retry with long gap.** Don't blanket-retry. | Provider outage. |
| `404` | Wrong URL | **Don't retry. Fix the URL.** | Typo in base_url. |
| `JSONDecodeError` | Truncated stream | **Retry the call, but check token limit — likely ran out mid-stream.** | Long output got cut at max_tokens. |
| `ValueError: ... has a context window of N tokens, below the minimum 64,000` (NEW 2026-07-03) | `auxiliary.compression.model` has a native context below Hermes' hard floor of 64K. Triggers in `agent/conversation_compression.py` `check_compression_model_feasibility`. | **Three-file fix, then `/new`:** edit `~/.hermes/config.yaml` (set `auxiliary.compression.model` to a 64K+ model), edit `~/.hermes/context_length_cache.yaml` (update the `<model>@<base_url>` entry — this file OVERRIDES config), then **restart the TUI** so the in-memory `load_config()` cache re-reads. Without the restart, the fix is on disk but the running process keeps using the old value. The error message itself offers "set `auxiliary.compression.context_length` to override the detected value" — that's a lie to Hermes's safety check; the model still truncates at its native limit. Don't trust it. Run `~/.hermes/patches/2026-07-03/swap-compression-model.sh <model> <ctx>` for an idempotent three-place edit. Verified choices for 16GB VRAM (2026-07-03): `qwen2.5:14b` (default), `llama3.1:8b-instruct-q5_K_M`, `mistral-nemo:12b`. Never use `qwen2.5:7b` — its 32K native context fails the check. | `compression_summary` tool fails on long conversation with `below the minimum 64,000` ValueError; gateway logs `turn-dispatcher exception` repeatedly. |
| `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f` (NEW 2026-07-03) | Subprocess worker output contains non-cp1252 bytes (Chinese, emoji, UTF-8 BOM). Python's default cp1252 codec on Windows crashes the reader thread. | **Patch the subprocess.Popen call to use binary streams + `io.TextIOWrapper(encoding="utf-8", errors="replace")`.** Hermes upstream bug in `tui_gateway/server.py` slash_worker (`_drain_stdout` / `_drain_stderr` methods). Patch script at `~/.hermes/patches/2026-07-03/reapply-server-encoding-fix.sh` reapplies it idempotently after every `hermes update`. Run it once now; re-run after `hermes update` to restore the fix. | `tui_gateway_crash.log` shows `thread exception · thread=Thread-XX (_readerthread) → UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f`. Subprocess worker stays dead; subsequent `slash` commands time out. |


## Pitfalls

- **API provider fallback chain is silent (NEW 2026-07-11).** See `references/2026-07-11-api-fallback-chain.md`. The chain on this host: `provider=minimax` (primary) → `provider=custom:yuanyuaicloud.cn` (fallback 1, attached credential pool) → `provider=custom:minnimax.chat` (fallback 2, different endpoint). Mid-conversation provider switches leave the agent with NO error and NO signal — only `~/.hermes/logs/agent.log` shows "Fallback to" / "Provider unreachable" lines. Distinguish retries (same provider, bounded 3) from fallbacks (different provider, silent). After any session that felt laggy or quality-shifted, run `grep -cE "Fallback to|Provider unreachable|Invalid API response \\(retry [0-9]+/3\\)" ~/.hermes/logs/agent.log` and report the count + timestamps. **Never claim "no errors I know of" without first running this probe** — the user's 2026-07-11 review caught an implicit "no" against evidence showing 2 fallbacks + 2 retries this session.
- **Don't blanket-add `sleep` for connection errors.** It doesn't help TCP-level failures. The Ollama `[::1]` bind issue wasted zero seconds of sleep but DID need `setx OLLAMA_HOST=0.0.0.0:11434` to actually fix. (NOTE: that fix is Windows-only — see the WSL2 bridge section below; if Ollama runs inside WSL2, the Windows `setx` has no effect.)
- **Don't trust fallback log labels over documented key state.** If memory says a key is invalid, but the log says "fallback to X worked," the actual X is probably a different backend, not the one you thought.
- **Pre-flight cost is ~0.5s and saves 5+ wasted calls.** Always worth it for any turn with >3 LLM calls.
- **On Windows: Git Bash mangles PowerShell argument parsing.** Use `cmd //c "tasklist /FI \"PID eq 1234\""` for process inspection, or write a .ps1 temp file. Never inline `$_` in bash one-liners.
- **NEVER run `pass show <cred>` without a subshell pipeline.** This is the 2026-07-11 incident lesson (see "Safe-FTP / safe-secret pattern" below). Even for one-off debugging, the verbose error output can echo the password. The first `pass show` must always go through the helper.
