# Bot-Challenge Gates That Block Verification Itself

When the *act of verifying* a tool's presence is itself gated by a bot-detection service, the inventory trichotomy needs a fourth state: **gated**. This reference captures the recurring pattern observed 2026-06-26 against joandrew.com.sg and its cPanel host.

---

## The failure shape

You run a verification step (REST probe, JSON-API login, Playwright navigation) and you get back:

- A 200 response with body `"One moment, please..."` + a `<script>setTimeout(reload, 5000)</script>` (the loader page)
- A Cloudflare Turnstile challenge iframe with `cf-challenge` markup
- A 403 with `server: cloudflare` and an HTML body that contains `cf-ray` headers
- A self-signed certificate error on the bare IP that *also* serves a loader page

Any of these = the verification itself is being challenged. The tool may be present; you just can't reach it through the gate.

---

## The four cases observed on joandrew.com.sg (2026-06-26)

| Endpoint | Method | Result | Diagnosis |
|----------|--------|--------|-----------|
| `https://joandrew.com.sg/wp-json/wp/v2/users/me` (with valid app password) | curl + Basic auth | **403 HTML** with `server: LiteSpeed`, no WP JSON signature | Cloudflare WAF rule blocking the egress IP. Tool is fine; my IP is bad. |
| `https://joandrew.com.sg/wp-json/` | curl no auth | 200, valid WP REST root | WP itself works |
| `https://joandrew.com.sg/wp-login.php` | curl no auth | 200, login page renders | WP login route is not gated |
| `https://sc134.sgcloudhosting.cloud/cpanel/login/?login_only=1` (POST creds) | curl | **404** on the JSON endpoint | The cPanel host's reverse proxy intercepts before cPanel sees it |
| `https://103.7.9.47:2083/login/?login_only=1` (POST creds, on bare IP) | curl | **200** with body `<title>One moment, please...</title>` + 5s reload JS | The cPanel daemon itself runs a JS bot-challenge before serving the login form |
| `https://103.7.9.47:2083/` (same, via Playwright + Chromium + ignoreHTTPSErrors) | real browser | Same "One moment, please..." loader page | The bot challenge detects automation fingerprint, not just IP |

**Net result:** Both the REST path to WP and the cPanel JSON-API path are gated. The only paths that work are FTP (no Cloudflare on the FTP port) and a few WP routes that don't go through Cloudflare's WAF.

---

## What this means for the inventory

If verification is gated, you have three options:

| Option | What it gives up | When to use |
|--------|------------------|-------------|
| **A. Wait out the rate limit** | Time (often 1 hour for sliding-window WAF rules) | When you don't need it now and the user is OK with a delayed start |
| **B. Ask the user to whitelist your egress IP at the WAF** | A one-time setup task for the user | When you'll need this verification many times in the session |
| **C. Find a non-gated path** | Time spent exploring (different port, bare IP, direct daemon) | When one exists (FTP is usually non-gated) |
| **D. Accept gated as the state and surface it** | The session can't proceed with this tool until unblocked | When no other path is available — surface to user, stop, let them choose |

The trichotomy extends from 3 to 4:

| State | Meaning | Action |
|-------|---------|--------|
| Verified present | Live check passed | Safe to invoke |
| Verified absent | Multi-path + CLI checks all returned 0 | Do not invoke |
| Unverified | Memory claims present, no live check done | Run verification first |
| **Gated** | Verification itself blocked by bot challenge or WAF | **Surface to user, stop, ask for whitelist / alternative path / wait** |

A gated tool is NOT verified_present (you can't prove it), and NOT verified_absent (you can't prove it isn't there either). It's its own state.

---

## The wording lesson (NEW 2026-06-26, user-corrected)

When you can't run verification, the temptation is to write "X is not available" or "Y doesn't work." Both are wrong framings when the truth is "I haven't started X yet" or "Y is gated by a bot challenge I can't solve from this session."

**The distinction matters because:**

| Wording | What the next session reads | What it implies about future attempts |
|---------|----------------------------|----------------------------------------|
| "Docker is not available" | Docker isn't installed | Don't try to start it |
| "Docker is installed; daemon stopped; needs admin elevation to start" | Docker is here, just needs one click | Try `Start-Service` or ask the user |
| "cPanel JSON-API returns 404" | cPanel doesn't have a JSON API | Don't try the bare IP |
| "cPanel hostname is Cloudflare-gated; bare IP serves a JS bot-challenge" | Two separate gates at two layers | Try other paths, ask user for IP whitelist, or surface and stop |

**The rule:** describe what you tried and what blocked you, not the tool's existence. The user can often solve "need to start Docker" in 30 seconds. They cannot solve "Docker isn't available" because that's a permanent state in your framing.

Verbatim user correction, 2026-06-26:

> "u said docker is not available it is u just never tried and assume it isnt be careful of your wording u should have said we havent started docker yet"

This applies to every "is X available?" question. Distinguish:

1. **Verified absent** (I checked, it's not there)
2. **Verified gated** (I checked, something is blocking the check)
3. **Not yet started** (the dependency exists but I haven't invoked the start step)
4. **Configuration missing** (the tool exists but needs setup I can't do alone)

These four states are not interchangeable. They imply different next actions.

---

## How to detect "gated" vs "absent" cleanly

When verification fails, before concluding "absent," check the response shape:

```python
def classify_verification_failure(response, body):
    if response.status == 200 and (b"One moment" in body or b"cf-challenge" in body or b"turnstile" in body.lower()):
        return "gated"  # bot challenge
    if response.status == 403 and b"cloudflare" in body.lower():
        return "gated"  # Cloudflare WAF
    if response.status == 200 and b"cpanel" in body.lower() and len(body) < 5000:
        return "gated"  # cPanel loader page
    if response.status == 404 and "json-api" in response.url:
        return "gated"  # cPanel reverse-proxy intercepted
    if response.status in (200, 301, 302):
        return "absent_or_other"  # genuine HTTP response, parse normally
    return "unknown"
```

This is a starting heuristic; refine per-host. The key is: don't classify a challenge page as a "not found" or "absent" result.

---

## Cross-reference

- `references/inventory-misuse-incidents.md` — the GEPA "we ran this yesterday" incident (the first failure this session)
- `wp-design-polish-via-css` SKILL.md Pitfall: Cloudflare + WP combination (same family of failure)
- `cpanel-shared-hosting-workflows` references/joandrew-session-2026-06-23.md — the prior joandrew session where Cloudflare 403 also fired during normal REST work
- `hermes-misbehavior-diagnosis` — when the agent reports "absent" but should have reported "gated," that's a misbehavior worth logging