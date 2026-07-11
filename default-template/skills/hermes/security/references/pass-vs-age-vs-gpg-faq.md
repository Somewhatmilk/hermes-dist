# Pass vs age vs GPG — User FAQ

The questions that came up in the session that moved this user from the age
path to the pass path. Useful both for onboarding and for the next time the
agent has to explain the choice.

## "Can pass and age work together?"

**Technically yes, but you don't want them to.** They solve the same job.
Running both means:
- two mental models (`~/.password-store/api/name.gpg` vs `~/.secrets/name.age`)
- two unlock flows (`pass` needs GPG passphrase; `age` needs the key file)
- you always wonder "which one is this secret in?"

**Don't run both. Pick one.** For a multi-platform + multi-device-sync user,
pass wins. Stick with pass; soft-delete every age template.

## "Multi-platform — does pass work on Linux/Mac?"

**Yes — pass is the Unix-native tool:**
- **Linux**: in every distro's repo (`apt install pass`, `pacman -S pass`, `dnf install pass`)
- **macOS**: `brew install pass`. Integrates with Keychain via gpg-agent.
- **Windows**: needs GPG4Win (or Git for Windows which bundles gpg). `pass` itself
  is installed via single-file copy from `git.zx2c4.com/password-store` (see
  `templates/hermes-pass-install-recipe.md`). Scoop/Choco/Winget don't ship `pass`
  as of 2026-07.

## "What does 'passphrase-based unlock' actually mean?"

`pass` requires you to TYPE your GPG passphrase to unlock secrets. `age` does
NOT — if someone reads the `age.key` file, they have everything.

```
pass:
  user types commands → pass show api/openrouter
                          ↓
                   "enter passphrase:"
                          ↓
                   user types [hidden]
                          ↓
                   secret prints for ~5s

age:
  user types commands → age -d -i ~/.secrets/age.key ...
                          ↓
                   secret prints immediately, no prompt
```

**Why it matters**: with `pass`, even if someone has your `~/.password-store/`
folder AND your `~/.gnupg/` folder, they still need your passphrase. With
`age`, if they have `~/.secrets/age.key`, done.

**Why it's a tradeoff, not a clear win**: if your disk is encrypted
(BitLocker on Windows, FileVault on Mac, LUKS on Linux), nobody reads
`age.key` without your disk password first. Passphrase-protection only adds
value when:
- disk is NOT encrypted, OR
- someone has your logged-in shell session AND can read files

For most people disk encryption handles it. But pass gives an extra layer.

## "Is it just one key, then per-secret forever after?"

**Yes.** One GPG key, used for all 12 secrets.

```
gpg --full-generate-key          ← run ONCE
pass init <your-email>           ← ONCE, links store to your key
pass insert api/openrouter       ← paste value, Ctrl+D twice
pass insert api/firecrawl        ← paste value, Ctrl+D twice
... 10 more times ...
                                  ↓
12 entries, ONE passphrase to unlock all of them
```

The GPG key IS the encryption key. You type the passphrase **once per cache
window** (gpg-agent caches it; set `default-cache-ttl 0` to cache for the
whole session), NOT per secret.

## "Do I need a real email address?"

**No.** The email is just an identifier that lives INSIDE your GPG key. Like
a username label. When you do `pass insert api/openrouter`, `pass` knows
which key to encrypt with. Nothing leaves your laptop. You can use any
string — even `foo@bar` — it doesn't have to be a working email.

## "Will a new session know about the secrets?"

**No, by design.**
- The encrypted `.gpg` files exist on disk forever (until you delete them).
- But they're useless without the passphrase.
- Each new terminal/shell session = new gpg-agent = starts with no cached passphrase.
- First time you (or the agent) reads a secret, gpg-agent prompts for the passphrase,
  or you set `default-cache-ttl 0` to cache until logout.
- After logout/shutdown, the cache is wiped. Type the passphrase again next session.

**For agents specifically**: when the agent process starts, it does NOT see
the secret values. It only sees the command structure. So even if the
agent's session log is leaked, the secrets are not in the log — only
`pass show api/X` invocations are.

**The agent invoking `pass` is safe because:**
1. Agent never reads `pass show` output (it pipes into the consumer).
2. Consumer (curl/python/discord-bot) gets the value in process memory.
3. If the consumer dies, memory is freed.
4. If the consumer writes the value somewhere → THAT'S the leak surface
   (audit the consumer's logging yourself).

## "What about credit cards / usernames / passwords?"

Yes, `pass` handles all of those:
```bash
pass insert bank/chase-card          # credit card number (no dashes)
pass insert login/gmail              # username/password combo
pass insert wifi/home-router         # wifi password
pass insert identity/ssn             # any PII
```

All encrypted with the same GPG key, unlocked with the same passphrase.

## "Does this also block the 2026 AI-agent attacks?"

**Partially.** The 4-rung ladder (`references/credential-4-rung-ladder-2026.md`)
maps directly:
- **CVE-2026-21852** (Claude Code → attacker `ANTHROPIC_BASE_URL` → key in
  Authorization header to attacker server): ✅ **blocked** — agent never has
  the key in env, only `pass show` calls. Attacker proxy never gets a real
  Authorization header.
- **Comment-and-Control** (April 2026, agent posts its own API key as PR
  comment): ✅ **blocked** — same reason.
- **Agentjacking** (Tenet, fake Sentry error → agent runs shell command with
  developer privileges): ❌ **NOT blocked** — the agent CAN shell-exec
  arbitrary commands regardless of where secrets come from. Mitigation for
  this one is sandboxing (separate user account, seccomp, Docker), not the
  secrets manager. Rung 2 stops here; rung 4 (broker proxy) is needed for
  full mitigation.

## "What gets cleaned up when I log out / shut down?"

With `default-cache-ttl 0`:
- gpg-agent process keeps the passphrase in RAM for the duration of its lifetime
  == until logout / shutdown
- On next login, you type the passphrase again on first `pass show` call
- Encrypted `.gpg` files on disk are unchanged (they're encrypted regardless)

Without `default-cache-ttl 0` (using the default `600`):
- gpg-agent prompts again after 10 minutes of inactivity
- Worse: in busy shell use, the cache might expire mid-task

## Cross-references

- Install recipe: `templates/hermes-pass-install-recipe.md`
- Loader shims: `templates/hermes-pass-loader-scripts.sh`
- Threat model + 12-key mapping: `references/credential-4-rung-ladder-2026.md`
- Mnemosyne redaction policy (USER HARD RULE): see memory_id
  `1bf87ee3bc5ca786` if loaded.
