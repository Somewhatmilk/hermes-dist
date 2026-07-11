# Browser automation: camofox vs CDP, and the workaround-mode rules

Reference for browser-driven research tasks on JS-rendered sites where the standard `browser_*` toolset doesn't expose the right control. Captures the camofox/CDP mismatch discovered 2026-06-19, the OpenAPI surface that does work, and the per-task budget rules the user added after watching the agent go off the rails trying to solve a combobox problem.

## The hard fact: camofox is REST-only, browser_cdp does not work with it

`browser_cdp` exists in the codebase at `hermes-agent/tools/browser_cdp_tool.py` (line 300 has `def browser_cdp(method, params, ...)`). It's listed in the default toolset at `hermes-agent/toolsets.py` line 49. **But** the source file's own comment at line 357-364 says:

> "No CDP endpoint is available. Run '/browser connect' to attach to a running Chrome, Brave, Chromium, or Edge browser, or set 'browser.cdp_url' in config.yaml. **The Camofox backend is REST-only and does not expose CDP.**"

So `browser_cdp` works against:
- Direct Chromium attach on `ws://localhost:9222` (the standard Playwright debug port)
- browser-use cloud (managed via Nous subscription)
- Browserbase / Firecrawl / similar managed backends with WS-CDP tunnels

It does **not** work against the camofox container at `localhost:9377`. The `browser_cdp` tool, if invoked when the active backend is camofox, returns `tool_error("No CDP endpoint is available... The Camofox backend is REST-only and does not expose CDP.")`.

Practical consequence: when the user is on camofox (their default, per `camofox: { ... }` block in `~/.hermes/config.yaml`), do not propose `browser_cdp` as a workaround for tasks that need native `<select>` interaction or arbitrary JS injection. It will not work.

## What camofox *does* expose

Camofox's openapi spec at `http://localhost:9377/openapi.json` documents these endpoints (relevant subset):

| Endpoint | Purpose | Useful for |
|----------|---------|------------|
| `POST /start` | Launch the camoufox browser process | Cold-start recovery when `browser_navigate` fails "No browser session" |
| `GET /tabs` | List active tabs in camofox's view | Discovery — may show empty `[]` even when the agent has navigated |
| `POST /tabs/{tabId}/evaluate` | Run JS in the page context | Set native `<select>` value, click-by-coordinate, anything Playwright doesn't expose |
| `POST /act` | Combined action with `kind: select_option` (or click/type/scroll/press/key/drag/hover) | Select option on a `<select>` without JS injection |
| `POST /tabs/{tabId}/navigate` | Navigate a tab | Cold-start recovery |
| `POST /tabs/{tabId}/click` | Click an element by ref | Same as agent's `browser_click` |
| `POST /tabs/{tabId}/screenshot` | Get a PNG of the current tab | Useful when `browser_snapshot` is missing elements |

All endpoints accept `userId` as a query/body parameter. The agent's standard `browser_*` tool wrappers use a `userId` internally that **may not appear in `GET /tabs`** — querying `/tabs` from outside the wrapper may return `[]` even when a session is active. This is the "camofox userId namespace" issue that confused the 2026-06-19 session: `browser_console` returned 403, and `curl` against `/tabs` showed empty, but `browser_navigate` worked fine.

## Working workaround: write a custom tool wrapper

When the standard `browser_*` tools can't drive a UI element (native `<select>`, shadow DOM, captcha), the path is:

1. **Confirm the tool actually doesn't work** (don't assume). `browser_console` failed for the agent in 2026-06-19, but `browser_cdp` also failed for a different reason (camofox backend). Don't conflate the two errors.
2. **If the standard tool blocks are tool-level (403, missing ref), STOP and report.** Per the per-task budget rule in `hermes-session-ritual`: max 3 tool calls to drive a single UI element, max 5 per sub-task, hard stop at 5 turns. Tool-level blocks are signals to STOP, not to escalate.
3. **If the user agrees to install a custom wrapper, write one** that calls the camofox REST API directly with the same userId the agent's wrapper uses. The wrapper is a 30-50 line Python module that exposes `browser_camofox_select(tab_ref_or_index, option_value)` and `browser_camofox_eval(expression)` to the agent. Register it in `toolsets.py` and `model_tools.py`. Done in a single setup session.

What the wrapper looks like (sketch — adapt the userId lookup to match the agent's existing wrapper):

```python
import os, json, urllib.request, urllib.error

CAMOFOX_URL = os.environ.get("CAMOFOX_URL", "http://localhost:9377")

def _get_user_id():
    # Match the userId the agent's browser_* tools use.
    # Read it from the hermes active-sessions DB or env var.
    return os.environ.get("HERMES_USER_ID", "default")

def camofox_evaluate(expression: str) -> str:
    """Run JS in the page context, bypassing Playwright gating."""
    # Find the active tab via GET /tabs?userId=<userid>
    tabs = json.loads(urllib.request.urlopen(
        f"{CAMOFOX_URL}/tabs?userId={_get_user_id()}").read())["tabs"]
    if not tabs:
        return "ERROR: no active tab for user"
    tab_id = tabs[0]["id"]
    req = urllib.request.Request(
        f"{CAMOFOX_URL}/tabs/{tab_id}/evaluate",
        data=json.dumps({"expression": expression, "userId": _get_user_id()}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    return urllib.request.urlopen(req).read().decode()

def camofox_select_option(tab_id: str, ref: str, value: str) -> str:
    """Set a native <select> option. No JS injection needed."""
    req = urllib.request.Request(
        f"{CAMOFOX_URL}/act",
        data=json.dumps({
            "userId": _get_user_id(),
            "kind": "select_option",
            "ref": ref,
            "value": value,
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    return urllib.request.urlopen(req).read().decode()
```

For one-off tasks, the agent can also call these directly via `terminal` + `curl`. Three-call budget, no source-code diving.

## Specific fix for the "native `<select>`" case

If a site uses native HTML `<select>` and the camofox snapshot doesn't expose the options as refs:

**Option A (preferred if installed):** use the custom `camofox_select_option` wrapper above. One call. Done.

**Option B (works without wrapper, browser_console must be working):**

```javascript
const s = document.querySelector('select');
const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
setter.call(s, 'HK');
s.dispatchEvent(new Event('change', { bubbles: true }));
s.dispatchEvent(new Event('input', { bubbles: true }));
```

The `Object.getOwnPropertyDescriptor` trick is required because React/Vue-controlled `<select>` elements ignore direct value assignment and only respond to the synthetic event sequence. Just doing `s.value = 'HK'` works for plain HTML but breaks on React-controlled forms.

**Option C (works without anything installed):** ask the user to do the click. 5 seconds of human interaction unblocks a task that would otherwise burn 30 minutes of agent effort. The 2026-06-19 xhxgame research session ran 12 turns trying option B / API-direct before the user asked "do u got the main model again," which was the signal to stop. The click would have taken one round-trip.

## Anti-patterns learned

- **Don't claim a tool "exists in the registry, just need a new session to use it."** The 2026-06-19 agent told the user exactly that about `browser_cdp` and was wrong — the tool's own source code says it does not work with camofox. A new session would have inherited the same problem.
- **Don't answer "do you have the main model again?" with 6 paragraphs of source-code investigation.** The user-side signal of that question is "the agent is going off the rails, not the model is broken." Stop, report, ask the user to do the click.
- **Don't paste user credentials into chat to "test" a workflow.** A persistent mistake from earlier in 2026-06-19: the user pasted Reddit/X/Discord passwords in chat as part of an age-vault setup. Those values are now in the session DB, terminal scrollback, and possibly the Mnemosyne RAG output as part of the `<memory-context>` block. The right flow is: user pastes values into the age-vault setup script via stdin; agent never sees plaintext.
- **Don't use `browser_navigate` mid-flow on camofox.** Per the user preference (load-bearing): once the browser is loaded, use snapshot/click/type only. Re-navigate wipes form state. Same rule applies even if the URL didn't change.
- **Don't conflate `hermes status` / `hermes skills list` output with secrets.** `hermes status` may show provider API keys in plaintext. The 2026-06-19 session saw the OpenRouter key `sk-o...db97` rendered. Rotate if shared.

## Linked references

- `hermes-session-ritual` — session-open probes (camofox container health is in scope); per-task budget rule for workaround mode
- `references/prompt-injection-patterns.md` — injection shapes that look like system context; the Mnemosyne `<memory-context>` block is one such pattern
- `references/owasp-llm-top10-mapping.md` — LLM05 (improper output handling) covers the "agent goes off the rails" failure mode
- `platform-accounts` skill — full credential workflow with camofox session reuse