## Secret Leak Workflow

What to do when plaintext credentials are discovered during a session — vault audit, file read, command output, or user paste. This is the playbook for "I just saw a token I wasn't supposed to see."

### Trigger conditions

- A `Keys.md`, `secrets.txt`, `.env`, or similar plaintext-credentials file is read during an audit
- A user pastes a token into chat (then rule #1 already fired — see hold-their-secrets)
- A grep across a directory returns tokens (OpenAI `sk-`, GitHub `ghp_`, HuggingFace `hf_`, Discord/Telegram bot tokens, AWS access keys)
- `git log -p` shows credentials in past commits

### Immediate response (3 actions, in order)

1. **Stop and surface.** Do NOT continue the tidy/move/edit work. Tell the user the file exists, what kind of tokens are in it (categories: bot tokens / API keys / passwords / refresh tokens), and that the values are already leaked because of prior `git commit && git push` cycles. Be specific about categories — don't echo values into chat.
2. **Do not echo values.** Never paste tokens back into the conversation, even partially. Never write them to a new file. Never include them in a memory or skill. The values are now compromised regardless of what you do with them in chat.
3. **Do not move/delete/encrypt the file without permission.** The user may want to inspect it before deciding. If the user already said "leave it, I know, just continue" — respect that and continue with the unrelated task; flag the keys file as out-of-scope.

### Recommended rotation order (when user is ready)

1. **Rotate every value in the file, in this priority order:**
   - **Discord/Telegram bot tokens** — these are the highest-impact: a leaked bot token lets an attacker act as your bot in your server/channels. Rotate via the developer portal token-reset button immediately.
   - **GitHub personal access tokens (`ghp_`)** — full repo access. Rotate via Settings → Developer settings → PAT → revoke + regenerate.
   - **HuggingFace tokens (`hf_`)** — model access. Rotate via Settings → Access Tokens.
   - **OpenRouter / OpenAI / Anthropic keys (`sk-`, `sk-or-`)** — billing-attached. Rotate via the provider's dashboard; check usage logs for unfamiliar consumption in the period since the file was first committed.
   - **Civitai, Reddit, X/Twitter, email-password combos** — rotate via each platform's password-reset flow; enable 2FA on every account that had a password exposed.
2. **Replace the file with the encrypted store** (`~/.hermes/credentials.gpg`, AES256-symmetric GPG; see `credential-management.md`). Write a thin pointer file at the original location (e.g. `Notes/Keys.md` → `~/.hermes/credentials.gpg` — see `gpg-gotchas.md` for the `gpg --batch --passphrase` invocation) so the user still has the workflow handy but the values are no longer in plaintext.
3. **Purge git history.** Even after the file is removed, every prior `git commit` is permanent. Use `git filter-repo --path Notes/Keys.md --invert-paths` (preferred over `filter-branch`, which is slow and error-prone) to rewrite history, then force-push. Confirm with the user before force-push — it breaks any other clones they have.
4. **Verify the purge.** `git log --all --oneline -- Notes/Keys.md` should return nothing. `git grep -l 'token-pattern-here' $(git rev-list --all)` should return nothing.

### After the leak is contained

- **Save the lesson, not the token.** Skills and memory entries about credential leaks must contain categories and procedures, never specific values. A `ghp_…` literal is exactly the kind of thing that will get copy-pasted into a future skill or memory entry by accident.
- **Recommend enabling pre-commit secret-scanning** (`gitleaks`, `trufflehog`, or `detect-secrets`) on the vault repo so future leaks are blocked at commit time rather than discovered in audit.
- **Recommend rotating the GPG passphrase** if the existing `~/.hermes/credentials.gpg` was set up with the same plaintext file as input — if the passphrase is short or shared across services, an attacker who now has access to the file (via past commits) might also be able to guess the passphrase.

### What NOT to do

- **Do not** save the credential values to memory (even as "for rotation tracking"). Memory persists across sessions and could be exfiltrated by a future session's read.
- **Do not** include the credentials in a `git commit` of the cleanup itself.
- **Do not** write the credentials to a new file "for the user to reference" — the values are already compromised, every new surface increases exposure.
- **Do not** run a token-validation API call (Discord API, Telegram BotAPI) on a leaked token in this session — the request itself shows up in the attacker's notification stream if they have the token too.

### Reproducer

This session (2026-07-05): vault audit of `C:\Users\somew\Desktop\Obsidian Vault\` surfaced `Notes/Keys.md` containing GitHub PAT, Civitai key, HF token, Discord bot token, Telegram bot token, Reddit password, X/Twitter login, email. The file was tracked by `Notes/.git/` (a private repo `Notes.git`) — values were in git history. User explicitly stated: "those are old keys im going to redact either way just continue on first and ignore that file." Correct response: surface categories + flag the leak, accept "ignore it" as a valid user decision, do not move or modify `Keys.md`, do not commit any cleanup that touches it.