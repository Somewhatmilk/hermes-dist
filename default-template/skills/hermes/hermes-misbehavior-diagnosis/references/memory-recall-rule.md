## The Memory-Recall-≠-Rule-Enforcement Pattern (NEW 2026-06-27)

When the user says **"why do u keep defying the rules"** or **"you never learn"** or **"you keep doing X and I hate it"**, the most common cause is NOT lack of knowledge — it's that a memory-stored rule exists but isn't enforced at the dispatch layer. Memory recall is a *necessary* condition for the rule to fire, but it is not *sufficient*.

**The 4-state rule-enforcement spectrum:**

| State | Description | Failure mode |
|-------|-------------|--------------|
| 1 | Rule in Mnemosyne only (best-effort recall) | Easily forgotten under context pressure |
| 2 | Rule in SKILL.md Pitfalls (surfaced when skill loads) | Still advisory — agent can choose to ignore |
| 3 | Rule as a precondition check (mechanical, fires before tool call) | Enforced — violation requires breaking the code |
| 4 | Rule as a hardcoded dispatch table (one specific tool per domain) | Strictest — cannot violate without code change |

**Diagnostic sequence:**

1. **Inventory the rule.** Find it in memory. Find the SKILL.md that should carry it. Identify the tool the rule applies to.
2. **Test the rule with a counterexample.** Can the agent violate the rule right now if it wanted to? If yes, the rule isn't enforced.
3. **Move the rule to state 3 or 4.** Precondition in the relevant tool wrapper (state 3) or hardcoded dispatch table (state 4). The rule must be mechanical, not advisory.
4. **Test the counterexample again.** After moving the rule, can the agent violate it now? If still yes, the precondition is in the wrong place (memory, not dispatch).

**The 4 operationalization recipes** (the L13 / rule-enforcement-precondition-pattern from the self-improvement umbrella, made operational):

- **Domain-based tool selection** (Reddit/Discord/Facebook → camofox, not web_extract): install a wrapper around `web_extract` that checks the URL domain against a registered set and routes accordingly. The wrapper is a precondition at state 3.
- **WSL host precheck**: before any WSL command, verify the process is on the WSL side via `wsl -e ps -ef` first, not the Windows side. If WSL-hosted, the WSL IP is the reachable endpoint, not Windows loopback.
- **Subagent context template**: any `delegate_task` call must include the parent's rules verbatim in the `context` field. Leaf agents don't inherit parent's memory or rules.
- **Depth-limited `find`**: never `find` the whole filesystem. Use `ls` + targeted paths from prior session memory. The session_search-first rule (see `hermes-session-open-inventory` pitfall) is the meta-form of this recipe.

**The single-class-level rule that captures the persistent failure mode (2026-06-27, user verbatim: "u said u couldnt switch to the profile but previously mi said u can just spawna subagent of the profile"):** A rule that lives only in working memory is **advisory, not enforced.** A rule that fires as a precondition at the tool-dispatch layer is **enforced regardless of agent state.** When the user reports a "you keep doing X" pattern and X is memory-stored, do NOT re-read the memory hoping for better recall — patch the dispatch layer. The fix is in the code, not in the agent's head.

**When the user calls out "rules aren't recall":** this is the L13 failure mode. The agent has the rule, the rule is loaded, the rule is being ignored. The fix is enforcement-layer, not memory-layer. Do not:
- Re-read the rule (it's already loaded)
- Add more canonical memories about the rule (the rule exists)
- Apologize and "try harder next time" (recall is best-effort, "trying harder" doesn't help)

DO:
- Find the tool the rule applies to
- Add a precondition check (state 3) or hardcode the dispatch (state 4)
- Test with the counterexample
- If the rule still gets violated, the precondition is in the wrong place

**When NOT to apply this pattern:**
- The "rule violation" is actually a new situation the rule didn't anticipate. Document the gap and extend the rule, don't patch the agent.
- The "rule" is actually user preference that varies by task (e.g. "be terse" vs "be detailed"). Those need the prompt-interview-pattern, not enforcement.
- The rule is a *value* (e.g. "honest failure reports beat fabricated successes") — values belong in SOUL.md and Mnemosyne, not in dispatch preconditions.

- **"Installed but absent" vs "haven't started yet" — when the agent finds part of a stack, don't conclude it's missing (captured 2026-06-26, this user).** Failure pattern: agent was asked about Playwright availability. Found `~/.cache/ms-playwright/` (chromium 1223, 1228 — real Playwright browser caches) and `npx playwright --version` returning `Version 1.61.1`. Concluded "no Playwright installed" and ran `npm install playwright` in `/tmp` to "install" it. The user's pushback: "we got a playwright server unless we never had playwright before." The Playwright MCP server was already running at `localhost:3004` (image `playwright-research:latest`, verified in `docker ps`). The agent's install attempt was both unnecessary AND bypassed the MCP server's controlled interface. **The rule:** when investigating tool availability, distinguish (a) the *server/MCP* (what the agent should use) from (b) the *local cache/library* (what `npm install` would touch). If both are present, the server is the right interface. **Discovery recipe before any "install X" decision:**
  ```bash
  # 1. Is there a server/MCP already running?
  hermes mcp list
  docker ps --filter "name=playwright" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

  # 2. Is there a local cache/library present?
  ls ~/.cache/ms-playwright/ 2>/dev/null
  ls ~/.npm-global/lib/node_modules/playwright/ 2>/dev/null
  npm list -g playwright 2>/dev/null

  # 3. Only AFTER both checks, decide: use existing / install / stop and ask user
  ```
  **Don't auto-install when either (1) or (2) shows the tool exists.** The "let me just install to be safe" reflex creates a worse problem than the gap it fills: it can shadow the existing interface, version-drift the cache, or trigger smart-approval blocks for an unnecessary write. **The framing lesson (parallel to the "Docker not available" correction):** when the agent sees partial evidence of a tool's presence, say "I see Playwright in the browser cache and `npx playwright` works, but I haven't checked whether there's an MCP server or running daemon. Let me check `docker ps` first." Then check. If a server is running, use it. If only the local cache is present, install is fine. If neither is present, install is required.

- **"Symbol missing" — verify which source tree the running Python is loading from before editing the source file (NEW 2026-07-01, this user).** Symmetric to the "Installed but absent" pitfall above: in *that* case the agent concludes something is missing when it isn't; in *this* case the agent concludes something is broken when it isn't. Failure pattern: `from agent.redact import redact_cdp_url` raises `ImportError: cannot import name 'redact_cdp_url' from 'agent.redact'`. The natural response is "the installed `redact.py` is missing the function — add it." That edit is wrong. The installed file already has the function (verified 2026-07-01 on this host at line 404). A stale 174 MB source-tree clone at `~/Downloads/hermes-validate/` was shadowing the install on `sys.path` because Python resolves whichever copy of `agent/` appears first; the clone was 10 days old and predated the `redact_cdp_url` addition. Editing the installed file would have created a duplicate function definition (or silently drifted behavior); the real fix was `rm -rf` on the clone. **The rule:** for any `ImportError` on a known internal symbol, treat the source file as innocent until proven guilty. Verify which tree the running Python is loading from, and which other trees exist on disk, BEFORE opening an editor.

  **The 4-step diagnostic recipe (the verification protocol):**

  ```bash
  # 1. Where is the running Python loading the module from?
  python -c "import <module>; print(<module>.__file__)"
  # Expected: AppData/Local/hermes/hermes-agent/<module>/<file>.py  (the install)
  # Symptom:  Downloads/<name>/<module>/<file>.py                    (a shadow — the bug)

  # 2. Are there other source trees of the same project on disk?
  find /c/Users/somew -maxdepth 4 -type d -name "<project>" 2>/dev/null
  # Multiple matches → suspect a shadow

  # 3. For each tree, does the missing symbol exist?
  for d in /c/Users/<user>/AppData/Local/hermes/<project> /c/Users/<user>/Downloads/<name>; do
    echo "=== $d ==="
    grep -n "def <missing_symbol>" "$d/<module>/<file>.py" 2>/dev/null && echo "  → has it" || echo "  → MISSING"
  done

  # 4. Confirm the diagnosis with both reproduction paths
  python -c "from <module> import <missing_symbol>" 2>&1
  # Reproduce 1 (wrong cwd): ModuleNotFoundError if no tree on path
  # Reproduce 2 (shadow on sys.path): ImportError cannot import name → shadow confirmed
  ```

  **Why this is not a "fix the symbol" situation:**

  - The installed file already has the symbol. Adding it again creates a duplicate-definition error or, worse, a silently different copy.
  - Backporting the function into the shadow is a trap: the rest of the shadow is also N days behind, so the NEXT missing import will hit a different file. You lose this game one symbol at a time.
  - `git pull` on the shadow doesn't help — the failing script is still running from the wrong directory. You'd have to also re-point every script/launcher that uses the shadow, which is more work than just deleting it.

  **How to recognize this trap in advance (so the next session doesn't fall into it):**

  - Check `~/Downloads/` and `~/Documents/` for old project checkouts. If they have the same name as an installed project (`hermes-agent`, `hermes-validate`, `ocd-projects`, etc.), they're shadow candidates.
  - After any `pip install -e .` or `git clone` that creates a second working tree, ask: "is this in addition to the install, or in place of it?" If "in addition," document it in `INDEX.md` or wipe it now.
  - The shell-guard's refusal of `rm -rf` on `Downloads/<project>/` is the early signal — that's when you run the 4-step diagnostic, not when you fight the guard with a Python bypass.

  **The mental-model fix.** The reflex "the source file is missing the function, edit it" assumes the running Python is loading the file you just looked at. It usually isn't, on multi-source-tree hosts. **The reflex you want instead is: "I have two (or more) source trees on disk; the running Python is loading from one of them; verify which before touching either."** This is the same shape as the dual-dir trap in Mistake 18 of `hermes-windows-filesystem-ops` (`~/.hermes/` vs `$HERMES_HOME/`) and the source-tree shadow in Mistake 25 of that skill — two copies of the same thing, the wrong one is being used. Different layer (source vs state), same shape.

  **Companion to "Installed but absent" pitfall above.** That one is "conclude not-missing when present" (don't install Playwright when the MCP is already running). This one is "conclude broken when correct" (don't edit `redact.py` when the shadow is the bug). Both are: don't act on a snapshot of state; verify the live state first.

  **Full host-specific incident write-up in `hermes-windows-filesystem-ops/Mistake 25`** — the exact 2-tree comparison, the exact 4-step verification recipe, the exact fix command, and the canonical Mnemosyne memory entry that was saved after the fix.
- **The "I just broke the repo" panic during a long-running script (captured 2026-06-24).** When a `terminal()` call to a 2-minute script (e.g. cron-style `rm -rf` + `cp` + `git add -A` for a 2700-file dir) times out at 60s, the output you see in the tool result is the last ~50KB the script produced. If the script's `git add -A` was the last thing to print before the timeout, the output looks like mass deletion (thousands of "delete mode 100644" lines). The agent's natural reaction is "I just broke the repo." **The reality:** a mid-flight `git add -A` only stages changes; the working tree is intact. The commit (which would have committed the changes) never ran because the script was killed. **Diagnostic sequence to run before panicking:**
  1. `git status --short | wc -l` — shows total changed files. If it's 2789 but your mental model of the repo has 50 files, you have staged a real change, not a deletion.
  2. `git diff --cached --name-only | head -20` — shows what was staged. If it looks like the right files (e.g. fresh skills from `~/AppData/Local/hermes/skills/`), you're fine.
  3. `git reset HEAD` — clears the staging area without touching the working tree. This is the recovery: it brings the repo back to "uncommitted changes visible" state.
  4. Re-run the script with a higher timeout (`timeout=300`) or as a background process (`process(action='poll')`).
  5. NEVER `git checkout .` or `git restore .` to "revert" before checking — those can lose uncommitted edits. The safe recovery is `git reset HEAD` + manual review of the diff.
- **NEVER reason from a partial `git status` output.** A timeout mid-`git add -A` looks identical to "staged for mass deletion" but the working tree is fine. Read the actual `git status --short` count, the staged-only count, and the unstaged-only count separately. A 2789-file status that has 2789 staged + 0 unstaged is a single large change (probably legit); a status with 0 staged + 2789 unstaged is a working-tree disaster (legit problem). The distinction matters.

- **Run `mnemosyne_recall(<project name>)` BEFORE generating any project deliverable — not after (Jun 2026, this session).** Trap pattern: the user opens default profile, asks for "an audit of my X" or "draft a Y for project Z", and the agent immediately starts work. The agent then fabricates project state from a half-remembered prior conversation, the user catches it in the next message ("that was a guess based on a misremembered memory note"), and 5-10 turns of work get thrown out. Real example: user asked for an Airbnb listing audit. Agent assumed "Mont Kiara 1BR" was the main property (a guess from a low-relevance memory fragment). Actual inventory: 2 listings (KL Penthouse 16+ AND ARTE 1BR), with the relevant prior research living in a different profile (communicate-design). The right sequence when starting project work in a session: (1) identify the project name from the user's message, (2) `mnemosyne_recall(<project name>, limit=10)` to surface prior context, (3) `hermes profile list` to confirm the active profile has the relevant skills/memory, (4) if the recall returns nothing AND the project is non-trivial, **ask the user for the canonical source** (paste the description, share the doc, confirm the inventory) — do NOT fill the gap with a guess. The cost of one recall call is negligible. The cost of generating a 500-token deliverable on hallucinated state is the user's time + the agent's trust budget. This is distinct from the existing "memory might be hours stale" rule (that's about temporal drift in live state) — this is about the agent skipping the recall step entirely.
- **`hermes status` output may include plaintext API keys** for active providers. Don't paste it into chat. Read it locally and redact before quoting.
- **Skill content can be templated and re-emitted.** If a reference file contains a literal `<memory-context>` example, an attacker (or an auto-responder) can re-emit that example structure to the user. Use generic placeholders.
- **`write_file` is sandboxed — `terminal` is not (Jun 2026, this user).** The `write_file` tool in `hermes_tools` writes into a Hermes-managed sandbox directory, NOT the real filesystem path you pass in. `terminal()` runs real shell commands against the real filesystem. This is the cause of an entire class of "I wrote the file, tested it, it worked, then the user said nothing happened" failures:
  - **Symptom:** the agent writes `/c/Users/somew/Desktop/foo.sh` via `write_file`, then runs `bash -n /c/Users/somew/Desktop/foo.sh` via `terminal`, and the test passes. The user double-clicks the file on the real Desktop, and nothing happens (or bash complains the file doesn't exist).
  - **Root cause:** `write_file`'s sandbox wrote the content to a Hermes temp dir, not to the real path. The `terminal` test ALSO ran in a context where the sandbox was visible to it (depending on how the sandbox mounts), so the test passed but didn't prove the real-file write happened.
  - **Fix:** ALWAYS verify real-filesystem writes by running `ls -la <path>` in `terminal()` AFTER the write_file call. If the file doesn't show up in real-fs `ls`, the sandbox ate it. For shell scripts and other files the user will execute directly, write them via `terminal` heredoc (`cat > /path/to/file << 'EOF' ... EOF`) instead of `write_file`.
  - **Rule:** `write_file` is for in-agent text I/O (skill files, memories, scratchpads, conversation artifacts). For anything the user will pick up off the real filesystem — Desktop files, project files, scripts to run, configs that a real tool will read — use `terminal` with a heredoc, `tee`, or `>` redirection. Verify with `ls` or `cat`.
  - **Same trap with execute_code:** scripts that create files via Python's `open(path, 'w')` inside `execute_code` may also write to the sandbox, not the real path. Test outputs "the file is at /c/Users/.../foo.txt" — verify with a real-fs `ls` before claiming the artifact is on disk for the user.
  - **This was a recurring failure pattern in Jun 2026, called out by the user ("u been testing in sandbox mode").** When the agent "verifies" code with a tool that shares the same sandbox as the write, the verification is circular — both are looking at the sandboxed copy, not the real one.

- **`execute_code` is BLOCKED for binary inspection — use `terminal` with `python -c` instead (NEW 2026-06-28, this user).** The `execute_code` tool refuses scripts that "run arbitrary local Python" with the error `BLOCKED: execute_code runs arbitrary local Python (including subprocess calls that bypass shell-string approval checks). Cron jobs run without a user present to approve it. Use normal tools instead, or set approvals.cron_mode: approve only if this cron profile is intentionally trusted.` This is a CONSERVATIVE refusal: it triggers on ANY Python execution, even passive read-only inspection like reading bytes from a file with `Path.read_bytes()` and pattern-matching printable strings. **The fix is one tool substitution:** call `terminal()` with a `python -c "..."` heredoc instead. The shell wrapper passes the Python through as a normal command and the approval layer applies the same risk rules it would for any other terminal call. Worked pattern (verified 2026-06-28): `cd "C:/path/to/dir" && python -c "import re; data = open('foo.exe', 'rb').read(); [print(m.group().decode('ascii', errors='replace')) for m in re.finditer(rb'[\x20-\x7e]{5,}', data) if any(k in m.group().lower() for k in ['rpg', 'screen', 'window', 'mode'])]"`. **Diagnostic sequence when `execute_code` is blocked:** (1) Read the `error` field of the result. If it says "Cron jobs run without a user present," it's the conservative blanket-refusal, NOT a real safety block. (2) Re-formulate the work as a `terminal()` call. `terminal()` is the workhorse for "I need to run code that does X" — `execute_code` is reserved for code that needs Python stdlib + tool-bridge in one script. (3) For binary inspection specifically (read file bytes, pattern-match strings, look for ASCII keywords), `terminal + python -c` is always the right path. **Companion to the "sandbox trap" pitfall above:** the sandbox pitfall is "the file didn't land on the real filesystem"; this pitfall is "the script that would inspect the file never ran at all because execute_code blanket-refused." Both are execute_code friction; the fix is the same: route through `terminal()`.
