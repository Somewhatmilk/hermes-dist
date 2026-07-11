# `.env` pointer pattern — the canonical answer to "agent leaked my secret from .env"

**Source of pattern:** r/hermesagent threads, July 2026. Confirmed in
[Accidental self-jailbreak of internal secrets on a one-shot prompt](https://www.reddit.com/r/hermesagent/comments/1ug0y38/accidental_selfjailbreak_of_internal_secrets_on_a/)
(machine-readable excerpts in `references/reddit-r-hermesagent-credential-patterns.md`).

## Why this exists

The `read_file`/`terminal` redaction in Hermes is a **filter, not a boundary**. An
LLM can decode the masked output by reading raw ordinals (verified by the
incident in the thread above — qwen 3.7 max walked past the asterisks by
decoding ASCII values in its head and handing the secret to the user). Once
the secret is in the model's context, no output redaction can stop it.

The only durable fix is: **the agent never holds the secret in a form it can
decode**. `.env` should contain POINTERS, not VALUES. Real values live in a
vault the agent cannot read. A launcher script outside Hermes's reach resolves
the pointers at process start and execs Hermes with real env populated.

## The pointer pattern

```bash
# ~/.hermes/.env — what the agent sees
OPENROUTER_API_KEY=pass:api/openrouter
DISCORD_BOT_TOKEN=pass:api/discord-bot
TELEGRAM_BOT_TOKEN=pass:api/telegram-bot
```

Format is `pass:<entry-name>`. The agent can read the `.env` all day; it only
sees pointers like `pass:api/openrouter` — useless without the GPG key.

## The launcher (resolves pointers → execs hermes)

```bash
#!/usr/bin/env bash
# ~/.hermes/bin/hermes-with-secrets.sh
# Wrapper that resolves pass: pointers in .env, populates the real env,
# then execs the hermes CLI. hermes never sees the resolution path.
SPEC=~/.hermes/secrets-spec.json
TEMP_ENV=$(mktemp)
chmod 600 "$TEMP_ENV"
cp ~/.hermes/.env "$TEMP_ENV"

while IFS=: read -r key value; do
  [[ "$value" == pass:* ]] || continue
  entry="${value#pass:}"
  real=$(pass show "$entry" 2>/dev/null) || continue
  sed -i "s|^$key=.*|$key=$real|" "$TEMP_ENV"
done < <(grep -E '^[A-Z_]+=pass:' ~/.hermes/.env)

set -a; source "$TEMP_ENV"; set +a
# Shred the temp env (urandom overwrite + unlink) before exec.
dd if=/dev/urandom of="$TEMP_ENV" bs=1 count="$(wc -c < "$TEMP_ENV" | tr -d ' ')" 2>/dev/null
rm -f "$TEMP_ENV"

exec ~/.hermes/hermes-agent/venv/Scripts/hermes.exe "$@"
```

Run hermes via this wrapper. On Windows, the bash script can be the target
of a shortcut, OR you can call it from a terminal that already has gpg-agent
running.

## Why this works

1. **The LLM can still read `~/.hermes/.env`** — the only thing it sees is
   `OPENROUTER_API_KEY=pass:api/openrouter`. No ordinal-decoding attack gets
   a usable secret.
2. **The resolution runs OUTSIDE the LLM's reach** — the launcher is a bash
   script. Hermes is exec'd as a child process, inheriting the resolved env.
3. **Real values are in `~/.password-store/api/*.gpg`** — gpg-encrypted at
   rest, decryptable only with the GPG passphrase. The agent never sees
   gpg-agent's prompt (it runs before hermes launches).
4. **`pass` itself is unchanged** — you still use `pass show api/X` for
   ad-hoc retrievals, `pass insert` for edits, `pass git init` for sync.

## Comparison with other approaches (from the same Reddit thread)

| Approach | What .env contains | How agent gets values | Blast radius if agent is compromised |
|---|---|---|---|
| Plaintext in .env (current) | real values | reads .env directly | every secret Hermes knows |
| `python-dotenv $()` substitution | real values resolved at runtime | **DOES NOT WORK** — python-dotenv is a literal parser (verified 2026-07-05, both `load_dotenv` and `dotenv_values` return the literal `$()` string, not the substituted value). | same as plaintext |
| `pass:` pointers + launcher | `pass:api/X` pointers | launcher script (outside agent) resolves at process start | only the pointers, which are useless without the GPG key |
| Bitwarden Secret Manager (bws) | one BWS token, all other creds in Bitwarden | BWS API at runtime (Nous Research ships this) | one BWS token; rotate that to invalidate everything |
| 1Password Connect | one Connect token, rest in 1Password | Connect API at runtime (per user `iamisseibelial`) | one Connect token, plus a Docker container with Tailscale |
| n8n / external workflow | no auth at all in Hermes | Hermes calls a workflow that holds the auth | nothing in Hermes |

For a single-host, self-hosted user, the launcher pattern is the smallest
blast-radius option that doesn't require external infrastructure.

## PITFALL — do NOT propose `$(pass show ...)` as a fix

This was the agent's first instinct (logged in Mnemosyne
`c1cfd2905ce391bc`). **It is wrong.** python-dotenv is a literal parser; it
does not evaluate `$()` or any shell syntax. Verified via:

```python
# smoke test that REJECTED option (c)
from dotenv import load_dotenv, dotenv_values
import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
    f.write('TEST_KEY=$(echo hello)\n')
    fname = f.name
load_dotenv(fname, override=True)
print(os.environ.get('TEST_KEY'))  # → '$(echo hello)', NOT 'hello'
print(dotenv_values(fname).get('TEST_KEY'))  # → '$(echo hello)'
os.unlink(fname)
```

If the user asks "how do I make .env fetch from pass automatically?", the
right answer is **launcher script with `pass:` pointers**, NOT `$()`
substitution.

## PITFALL — gpg-agent cache must outlive the launcher

The launcher calls `pass show` once per env var. If gpg-agent isn't running
or has expired, you get N pinentry popups on launch. Fix once:

```bash
echo "default-cache-ttl 86400" >> ~/.gnupg/gpg-agent.conf
echo "max-cache-ttl 86400"     >> ~/.gnupg/gpg-agent.conf
gpgconf --kill gpg-agent
```

Then enter the GPG passphrase once per day.

## PITFALL — write-blocked files (the agent can't edit .env for you)

`~/.hermes/.env` is write-blocked for the agent (per the credential-guard
table in `hermes-profile-taxonomy`). The user must manually replace the
plaintext values with `pass:api/X` pointers. Tell them the exact find-replace
block. Don't try to bypass the guard — the user has reviewed the file and
chosen this constraint.

## Related

- `references/credential-4-rung-ladder-2026.md` — 4-rung ladder with
  this pattern as rung 3 (out-of-band resolution).
- `references/pass-batch-migration-recipe.md` — initial migration of values
  FROM plaintext .env TO encrypted pass store.
- `templates/hermes-pass-loader-scripts.sh` — `hermes-pass-secret.sh` and
  `hermes-env-load.sh` shims (used by the launcher above for bulk resolution).
- `references/reddit-r-hermesagent-credential-patterns.md` — the source
  threads, with machine-readable excerpts of the relevant comments.
