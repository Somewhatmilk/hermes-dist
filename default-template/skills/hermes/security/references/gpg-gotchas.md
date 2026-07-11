# GPG Gotchas Encountered This Session

## "File exists" when overwriting
```
gpg: symmetric encryption of '[stdin]' failed: File exists
```
**Fix:** `rm -f ~/.hermes/credentials.gpg` before re-encrypting. GPG refuses to overwrite by design.

## AES256-CFB on Windows
GPG on git-bash (MSYS2) uses AES256-CFB by default. Verify with:
```bash
gpg --decrypt < file.gpg 2>&1 | head -1
# → "gpg: AES256.CFB encrypted data"
```

## Passphrase via stdin
Use `--batch --passphrase-fd 0` to pipe passphrase. Without `--batch`, gpg may prompt interactively and hang.

## Empty file initial state
Fresh `credentials.gpg` may exist but contain `{"credentials": {}}`. Always decrypt and inspect; don't assume non-zero file size means real data is present.

## "Sorry, we are in batchmode - can't get input"
```bash
$ gpg --batch --decrypt secret.gpg > out.txt
gpg: Sorry, we are in batchmode - can't get input
```
**Cause:** gpg needs to unlock the private key (passphrase), but the agent has no TTY to pop pinentry, AND gpg-agent's passphrase cache is empty. `--batch` blocks any interactive prompt.
**Fix:**
1. Have the user run `gpg --clearsign < /dev/null` in their own terminal ONCE per session to prime the cache.
2. Confirm `~/.gnupg/gpg-agent.conf` has `default-cache-ttl 0` so the priming holds until logout.
3. After priming, `gpg --batch --decrypt` works without prompting.

## `--quiet` does NOT suppress metadata lines
`gpg --decrypt` with `--quiet` STILL prints metadata like
`gpg: encrypted with rsa4096 key, ID 39D39..., created YYYY-MM-DD`
to stderr. When stderr is captured into the same variable as stdout
(via `$(gpg ...)` command substitution), the metadata mixes with
the plaintext and corrupts length checks.
**Fix:** Decrypt to a tempfile via redirection, then `wc -c < tempfile`:
```bash
tmp=$(mktemp)
gpg --batch --yes --quiet --decrypt secret.gpg > "$tmp" 2>/dev/null
actual=$(wc -c < "$tmp" | tr -d ' ')
rm -f "$tmp"
```
Never `wc -c` after `$(gpg ...)` capture if metadata may be present.

## `pass insert` always opens a TTY — don't script it
The `pass` bash script's `cmd_insert` function uses `read -s` to
prompt for the secret (line 463). It does NOT respect piped
stdin even with `allow-loopback-pinentry` in `gpg-agent.conf`.
**Fix:** call `gpg --encrypt` directly to write the `.gpg` file,
bypassing `pass insert` entirely. See
`references/pass-batch-migration-recipe.md` Step 2 for the working
loader script.

## `--batch` and `--pinentry-mode loopback` are mutually exclusive on DECRYPT
```bash
# ❌ breaks — batchmode blocks input, loopback mode expects input
gpg --batch --yes --pinentry-mode loopback --decrypt secret.gpg
# → "gpg: Sorry, we are in batchmode - can't get input"
```
**Cause:** `--batch` means "never read input". `--pinentry-mode loopback`
means "read passphrase from stdin (or fd)". They contradict. `--batch`
wins → loopback becomes a no-op → no input source → fail.

**Fix:** for decrypt verification, drop `--batch`. Use plain
`gpg --yes --quiet --decrypt ... > "$tmpfile"`. gpg-agent then prompts
via the cached passphrase (if primed in Step 0 above) without needing
`--pinentry-mode loopback`. Encrypt-side is different — encrypt doesn't
touch the private key, so `--batch` is fine there.

```bash
# ✅ correct — encrypt side (no TTY needed)
printf '%s' "$val" | gpg --batch --yes --quiet --pinentry-mode loopback \
  --trust-model always --encrypt --recipient "$FPR" --output "$out"

# ✅ correct — decrypt side (uses cached passphrase via gpg-agent)
gpg --yes --quiet --decrypt "$out" > "$tmpfile"
actual=$(wc -c < "$tmpfile" | tr -d ' ')
```

If you mix `--batch` and `--pinentry-mode loopback` on decrypt, length
verification returns 0 bytes for every entry — same surface symptom as
"gpg-agent not primed" but cause is the flag conflict.

## HARD INVARIANT — never pipe decrypted plaintext into agent context
```bash
# ❌ LEAK — plaintext flows into terminal scrollback + Hermes tool capture
gpg --decrypt secret.gpg | head -3
gpg --decrypt secret.gpg | cat
pass show api/x | head -1

# ❌ LEAK — even without echo, value is in tool output if you redirect
# then read back
gpg --decrypt secret.gpg > /tmp/out.txt
cat /tmp/out.txt    # value is now in chat/tool result
```
**Why:** pipe to ANY consumer (`head`, `cat`, `less`, file-then-read,
`wc -c` AFTER reading the file) → plaintext ends up in tool result →
LLM context → may be echoed back OR persisted in session DB.

**The only safe patterns**:
- `wc -c < $tmpfile` where `$tmpfile` was written by gpg's stdout
  redirect (gpg's stderr warning is on fd 2, not fd 1, so the file
  contains plaintext only).
- pipe plaintext to a DIFFERENT consumer (curl, sqlite, ffmpeg) that
  does NOT report the bytes back.
- `pass show api/x | curl ...` works — curl's response is what comes
  back, not the secret.

**Required cleanup after a safe temp-file verify:**
```bash
dd if=/dev/urandom of="$tmpfile" bs=1 count="$(wc -c < "$tmpfile" | tr -d ' ')" 2>/dev/null
rm -f "$tmpfile"
```
SSDs with wear-leveling make unlink non-secure, but the overwrite is
cheap defense-in-depth.

**Incident 2026-07-05:** agent ran `gpg --decrypt api/openrouter.gpg |
head -3` to "verify cache state" — openrouter API key flowed into
chat context. Plaintext values are never acceptable in agent context,
even for one-shot diagnostic use. The verification pipeline in
`references/pass-batch-migration-recipe.md` Step 2 is correct — do
not "tee", "tail", or otherwise expose the plaintext for any reason.
