# BYO-Agent Template (Mode 1 — Plugin)

This is a starting point for users who want to ship their own agent code
while reusing the operator's runtime. Drop a Python module into
`~/.hermes/profiles/<uuid>/agents/<your-agent>/__init__.py` and it will
auto-load at session start.

## File: __init__.py

```python
"""My custom agent — extends operator's Hermes with my own tools + skills."""

# ─── 1. Import operator's skills (read-only, via the hermes.skills facade) ─
from hermes.skills import web_search, image_gen, memory  # operator's skills

# ─── 2. Define your own tools ─────────────────────────────────────────────
def my_tool(query: str, limit: int = 5) -> dict:
    """A custom tool wrapping operator's web_search."""
    return web_search(query=query, limit=limit)

def my_summarizer(text: str) -> str:
    """Custom summarizer — uses operator's memory skill for context."""
    ctx = memory.recall(query=text, limit=3)
    return f"Context: {ctx}\nSummary: {text[:200]}"

# ─── 3. Override or extend SOUL.md trigger phrases ───────────────────────
# (SOUL.md at ~/.hermes/profiles/<uuid>/SOUL.md can declare trigger phrases
# that auto-load this agent's tools when matched.)

# ─── 4. Per-user capability token (if you want stronger scopes) ─────────
# Run `hermes login --operator operator.tail.ts.net` to get a token.
# Store in ~/.hermes/.operator-token. Default scopes include tools.web_search
# but NOT tools.docker_run or profile.config_override. To opt-in to those:
#   hermes login --scope tools.docker_run --scope profile.config_override
