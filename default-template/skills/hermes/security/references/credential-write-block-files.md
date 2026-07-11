# Credential / Security Files That Are Write-Blocked for Agents

When the agent tries to edit these files, the write is denied with a clear
error. **The user must edit them manually** (via editor, `hermes config`,
or `scoop`/`choco`/etc. where applicable).

## Why this guard exists

Some files hold enough power to compromise the entire runtime if the agent
mis-edits them, prompts get hijacked, or a partial write corrupts state.
The user maintains ownership of these files; the agent can READ most of
them, just not WRITE.

## Known write-blocked files (verified 2026-07-05)

| File | Why write-blocked | How user edits |
|---|---|---|
| `~/.hermes/.env` | Holds all API tokens. Agent reading them isn't great either; writing = instant leak surface. | `notepad ~/.hermes/.env` (or any editor), or `hermes config set …` for individual keys |
| `~/.hermes/config.yaml` | 73 sections / 331 leaf keys. One wrong indent breaks Hermes startup. Agent bypass = footgun. | `hermes config edit`, `hermes config set`, or manual editor after backup |
| `~/.gnupg/gpg-agent.conf` | Controls gpg-agent's passphrase cache + pinentry policy. Wrong value → lock user out of `pass` store. | Create file if absent (Windows often has no `~/.gnupg/` after fresh install), edit via Notepad |
| `~/.gnupg/private-keys-v1.d/*.key` | Private GPG keys. Agent edit = key compromise. | Use gpg tooling (`gpg --edit-key`, `gpg --export-secret-keys`) |
| `~/.gnupg/openpgp-revocs.d/*.rev` | Revocation certificates. Burning one invalidates the GPG key. **Also: store OFF-LAPTOP** (USB / paper / cloud) so a stolen-laptop event doesn't burn a usable revocation cert. | gpg tooling for regen; mv to safe storage for archive |
| `~/.password-store/.gpg-id` | Tells `pass` which GPG key encrypts the store. Wrong value = silent decrypt failures on every `pass show`. | `pass init <new-fpr>` regenerates |
| `~/.hermes/secrets-spec.json` (planned) | Maps env-var names to pass-store paths. Wrong mapping = wrong secret injected. | Direct edit by user; the agent should propose a diff for review |

## What the agent CAN do

- READ any of these via `terminal` (the terminal tool's blocked-write check
  is on `write_file`/`patch`, not on `cat`)
- Diff and propose changes verbally in chat
- Generate a "ready-to-paste" block the user copies into the file
- Run `hermes config …` CLI commands on `config.yaml` (read & edit paths)
- Test that changes work AFTER the user has applied them

## Standard recipe when user hits the block

1. Agent detects write-block: surface the exact file + reason + the exact
   content the user should add
2. Wait for the user to confirm they applied the edit
3. Agent verifies by re-reading the relevant sections

Example surface message:
> That file is write-blocked for me (same class as `~/.hermes/.env` —
> holds security state I shouldn't author unilaterally). You'll need to
> create/edit it. Content:
> ```
> allow-loopback-pinentry
> default-cache-ttl 0
> max-cache-ttl 0
> ```
> Save to `C:\Users\somew\.gnupg\gpg-agent.conf`, then run
> `gpgconf --kill gpg-agent` and tell me "done".

## Detecting new write-blocks

If `write_file` returns "Write denied: … is a protected
system/credential file" on a path the agent didn't expect, log it as a
candidate addition to this list. The pattern tends to be: any file that
- holds credentials, tokens, keys, or
- controls agent behavior at startup, or
- would require deep structural knowledge (YAML/JSON indent, GPG syntax)
  to edit safely.

## Related

- `templates/hermes-pass-install-recipe.md` — explicitly references this
  list in Step 4
- `references/pass-vs-age-vs-gpg-faq.md` — answers "will a new session
  know about secrets"
