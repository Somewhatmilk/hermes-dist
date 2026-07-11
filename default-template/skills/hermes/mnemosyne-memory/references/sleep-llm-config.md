# Mnemosyne Sleep / LLM Consolidation Config

## The default consolidation LLM is broken

**Symptom:** `mnemosyne sleep` runs without error but produces no useful output. The LLM-backed consolidation silently does nothing because the default `MiniCPM5-1B-Q4_K_M.gguf` model (per `mnemosyne/core/local_llm.py`, line 19-20) **cannot be loaded** — the venv lacks `llama-cpp-python` (or `ctransformers` as the fallback). The local LLM path returns `None`, the sleep call completes with `status: no_op` or empty output, and no error is surfaced to the user.

## The fix — route consolidation to ollama

Add to `$HERMES_HOME/.env`:

```bash
MNEMOSYNE_LLM_ENABLED=true
MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:11434/v1
MNEMOSYNE_LLM_MODEL=qwen2:0.5b
MNEMOSYNE_LLM_API_KEY=ollama
```

`ollama serve` must be up with the model pulled: `ollama pull qwen2:0.5b`. With this config, `mnemosyne sleep` will hit the ollama HTTP endpoint instead of trying to load the broken local GGUF.

## Why qwen2:0.5b (head-to-head on this host)

| model | time | facts captured (of 5) | notes |
|---|---|---|---|
| `MiniCPM5-1B-Q4_K_M` (default) | 0.0s | **0/5 — empty** | backend not installed; silently fails |
| `qwen:0.5b` (original Qwen) | 11.2s | 1/5 | doesn't consolidate, just lists facts |
| `qwen2:0.5b` | 7.8s | **5/5** | proper consolidation, uses pronouns to refer to user |
| `qwen2:0.5b` (warm cache) | 0.4s | **5/5** | second call onward |
| `qwen2.5:0.5b` | 1.9s | 5/5 | but just concatenates with semicolons inside `[...]`, not real consolidation |

The Reddit post that prompted this test (`r/hermesagent/comments/1tms3g6`, "Memory Providers: I tested them all") recommended qwen "0.8b" — that variant doesn't exist. The author likely meant `qwen2:0.5b` (the older Qwen 2 arch beats Qwen 2.5 on consolidation tasks despite being smaller).

## What about the bundled MiniCPM model?

The model file is still useful to download for reference (~688MB), but it stays unusable until the user installs `llama-cpp-python` (or `ctransformers`) into the hermes venv. The fix for "I have a 1B Q4 local model and it doesn't work" is one of:
- `pip install llama-cpp-python` in the hermes venv, OR
- set the ollama env vars as above

The ollama path is faster, simpler, and doesn't pollute the venv.

## Mnemosyne priority order for LLM calls

From `mnemosyne/core/local_llm.py` line 580+:

1. **Host LLM backend** (if `MNEMOSYNE_HOST_LLM_ENABLED=true` and registered)
2. **Remote OpenAI-compatible API** (if `MNEMOSYNE_LLM_BASE_URL` is set) ← ollama sits here
3. **Local GGUF** (if not disabled) ← broken path; avoided when env vars above are set

The env-var config above puts the ollama call on path 2, so the broken local path 3 is never tried.

## Verification

After the env vars are set, run `mnemosyne sleep` in a state where there ARE old working memories. The output should show non-empty `Consolidation complete: ...` JSON. If it still says `no_op` with empty changes, the env vars didn't propagate (fresh shell that didn't source `.env`); restart the process or `source ~/.hermes/.env` first.

## Cross-references

- `mnemosyne-memory/SKILL.md` — main skill, working config block.