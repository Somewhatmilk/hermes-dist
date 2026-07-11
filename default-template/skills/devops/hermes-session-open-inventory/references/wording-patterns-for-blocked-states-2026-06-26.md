# Wording Patterns for Verification Blocked States

When the agent cannot directly verify something — Docker daemon stopped, tool gated by a bot challenge, credential missing, service unreachable — the wording of the report matters more than the verdict. The wrong wording hardens the state into "permanently absent" in the user's mental model (and in subsequent agent turns that re-read this transcript). The right wording preserves a solvable path forward.

This reference is the user-corrected version of a pattern that burned the 2026-06-26 session. **Original failure:** agent reported "Docker is not available" when the truth was "Docker Desktop is installed but the daemon isn't running and the user needs to click one button to start it." The user corrected: "u should have said we havent started docker yet." That correction is the rule this file captures.

## The 4 wording classes

When a verification step fails, classify the failure into one of these four buckets. **Pick the bucket and use its template wording exactly.** Don't invent new wording — these templates have been stress-tested against the user's mental model.

### 1. `Not-yet-started` (most common, easiest to solve)

**What it means:** the dependency is installed, configured, or available; only the action of starting/using it is missing. One user click or one terminal command resolves it.

**Symptoms:**

- Tool binary exists at the expected path
- Configuration file exists
- The daemon isn't running (no `docker info` response, no `hermes gateway status` reply)
- Or the action simply hasn't been performed yet (a script that needs to be invoked)

**Template wording:**

> "[Tool] is installed at [path] but [the specific state] isn't active yet. [One sentence describing what the user needs to do, with an estimated time]. After that, [what will be possible]."

**Worked examples:**

- ❌ BAD: "Docker is not available."
- ✓ GOOD: "Docker Desktop is installed (binary at `C:\Program Files\Docker\Docker\Docker Desktop.exe`), but the daemon isn't running yet — `docker info` returns 'cannot connect to Docker engine.' The user can start it from the Start menu (one click, ~30s for the daemon to initialize). After that, `camofox-browser` and the 7 other containers listed in the previous session's `docker ps` should be reachable."

- ❌ BAD: "Can't run camofox from this session."
- ✓ GOOD: "camofox-browser is the container I need, and it was Up 6 minutes in the last session per `docker ps`. I haven't checked whether it's still Up. Run `docker ps --filter name=camofox-browser` to confirm before assuming the container is alive."

- ❌ BAD: "The cPanel daemon is unreachable."
- ✓ GOOD: "The cPanel JSON-API login at `https://sc134.sgcloudhosting.cloud/cpanel/login/?login_only=1` is gated by Cloudflare Turnstile (the HTML response is the JS loader page, not the actual login form). The bare-IP daemon at `https://103.7.9.47:2083/` is gated by cPanel's own JS bot-challenge. Camofox at `:9377` can defeat both because its egress IP and Firefox fingerprint pass — I haven't tried camofox yet."

### 2. `Gated` (blocked by infrastructure that has a known workaround)

**What it means:** the tool is reachable, but a layer between the agent and the tool is blocking access (Cloudflare WAF, bot challenge, IP block, rate limit, captcha, JS-only login).

**Symptoms:**

- HTTP 403 with HTML body (Cloudflare/WAF) rather than JSON 401 (genuine auth failure)
- HTTP 200 with a JS loader page (`<title>One moment, please…</title>`, `window.location.reload()` setTimeout)
- HTTP 429 with `Retry-After` header
- TCP connection succeeds but TLS handshake fails with `certificate verify failed`

**Template wording:**

> "[The resource] is gated by [specific gate name, e.g. 'Cloudflare Turnstile on the hostname', 'cPanel JS bot-challenge on the bare IP']. [Symptom observed, e.g. 'the loader page returns instead of the login form']. Workaround: [specific workaround, e.g. 'camofox at :9377 uses a different egress IP and a Firefox fingerprint that typically passes the gate']. I haven't tried the workaround yet."

**Why this matters:** "Gated" implies a path forward (try the workaround, whitelist the IP, wait for the cooldown). "Blocked" implies no path. Most users will solve a gated condition in under a minute if you tell them what to try.

### 3. `Configuration-missing` (needs the user to add a value)

**What it means:** the tool exists, the dependency exists, but a required configuration value (env var, credential file, API token) is not present.

**Symptoms:**

- `~/.hermes/auth/foo.env` is missing
- An env var referenced in code is undefined
- A config file is missing a required field

**Template wording:**

> "[Tool] is installed and the binary is reachable, but [specific configuration] is missing. [Where it should be, what it should look like, and how the user can provide it]. I won't proceed without it because [consequence]."

**Worked example:**

- ❌ BAD: "I can't access the database."
- ✓ GOOD: "phpMyAdmin is reachable at `cpsess.../sql/PhpMyAdmin.html` from the cPanel dashboard (logged in via camofox), but the DB credentials aren't in `~/.hermes/auth/joandrew-db.env`. To run the SQL queries for the 10-fault audit, paste the DB user + password into that file (the user already exists; my pre-flight showed the table prefix is `wphe_` from `wp-config.php`)."

### 4. `Absent` (genuinely not there — last resort)

**What it means:** after a multi-path filesystem scan, after checking known install locations, after verifying the user's home directory and standard system paths, the thing is genuinely not present.

**Symptoms:**

- `which <tool>` returns empty
- `find ~ /usr/local /opt -name "<tool>"` returns 0 matches
- The expected config file does not exist and no .bak / .old version is found
- A package manager check (`apt list --installed`, `pip show`) shows it's not installed

**Template wording:**

> "[Tool] is not present on this system. I checked [list of paths/commands run]. To install: [specific install command]. Want me to attempt the install, or do you want to do it yourself first?"

**Why "absent" is the last resort:** because the user can usually resolve not-yet-started in seconds, and gated in a minute or two. Only after you've eliminated those two should you conclude absent. If you jump to absent too early, you'll often be wrong, and the user will spend time installing something they didn't need to.

## Self-check before sending any "not available" report

Run through this checklist before writing any verdict:

1. Did I check `which <tool>`, `where <tool>`, `command -v <tool>`? (PATH-level search)
2. Did I check the install dir + sibling install dirs + user home? (multi-path filesystem scan — see the inventory skill)
3. Did I check whether the daemon/service is just stopped? (`docker info`, `Get-Service`, `hermes gateway status`)
4. Did I check whether the response I got is a JS loader, a bot challenge, or genuine absence? (HTML body with "One moment, please…" ≠ "this tool doesn't exist")
5. Did I distinguish between "this resource is gated by X" and "this resource is absent"?

If I answered "no" to any of these, I haven't finished the diagnostic. Run the missing step before reporting.

## The 4 forbidden phrasings (and their replacements)

These are the phrasings the user has explicitly flagged as wrong, captured from real session corrections:

| Forbidden | Replace with | Why |
|-----------|--------------|-----|
| "X is not available" | "X is installed but [specific state] isn't active yet" | The first implies permanent absence; the second preserves a solvable path. |
| "I can't use X" | "I haven't tried X yet" or "X is gated by [specific gate]" | The first frames as agent limitation; the second frames as solvable. |
| "X doesn't work" | "X is reachable but [specific behavior] doesn't match what I expected" | The first is a verdict; the second is an observation that invites debugging. |
| "Need admin" (without specifying what to start) | "Docker Desktop daemon is stopped. Start it from Start menu → Docker Desktop (one click, ~30s)" | The first leaves the user guessing; the second gives a 30-second fix. |

## The user-preference embedding (meta-rule)

The user's preference here is **diagnostic framing**, not just wording. When verification fails, the report should:

1. State what was checked
2. State what was found (or not found)
3. State the most likely cause class (not-yet-started / gated / configuration-missing / absent)
4. State the next action that resolves it (specific command or click)
5. Estimate the time for resolution

The 5-step structure applies to every "I can't reach X" report, not just Docker. The user has corrected this pattern multiple times. The corrected pattern is now codified in the SKILL.md as the "wording trap" pitfall.

## When NOT to use these patterns

These templates are for **verification failures the user might be able to solve.** Don't use them when:

- The user explicitly asked "is X available?" and the answer really is "no" (e.g. "is `slack-cli` installed?" and the answer is genuinely no — say so plainly)
- The verification is part of an internal pipeline that the user doesn't control (e.g. a third-party API rate limit that's not their problem)
- The user is asking a meta-question about their setup and wants a direct answer (don't pad with the 5-step diagnostic when they just want "yes/no")

The 5-step structure is the default for blockers. Direct answers are fine when the user asks for them.