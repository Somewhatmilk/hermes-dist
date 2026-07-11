# Anti-pattern: Validating a complaint about a file that does not exist

**Status:** NEW 2026-07-11, this user. v2.10.0 candidate for `hermes-misbehavior-diagnosis`.
**Family:** positive-claim cousins (extended). Sibling to `predicting-a-cause-without-running-the-diagnostic` (predicts without testing), `bug-hypothesis-before-canon-check` (claims NEW BUG without canon), `investigation-as-narration` (narration over answer), and `claiming-credit-for-an-edit-you-didn't-make` (claims authorship without verifying on disk).

## The pattern

An AI agent (subagent, prior session, or new prompt) issues a complaint
that names a specific file and a specific patch, e.g.:

- "Add patch: replace `git diff --quiet` with `[ -z \"$(git status --porcelain)\" ]` in `sync-backup.sh`"
- "Update `~/.hermes/scripts/sync-backup.sh` line 42 — the MSYS path breaks"
- "The handshake config in `/etc/handshake/wsl-windows.yaml` is wrong"

The complaint is **plausible-looking**: it cites a real-sounding file,
a real-sounding line, a real-sounding failure mode. The agent being
asked to act on it then writes a long analysis of the proposed fix,
quotes a prior incident memory about the same failure mode, and
recommends applying the patch.

**But the file does not exist on disk.** The patch is untargetable.
The analysis is correct in general but **answers a question about a
phantom artifact**. The right move on the first turn is: search the
disk and confirm the file is or isn't there, **before** writing any
analysis. If it isn't there, the complaint is REFUTED at the file-
existence layer, and the rest of the analysis is moot.

## The 2026-07-11 incident (this user)

**Setup:** The user delegated three "AI agent complaints" (G12, G13, G14)
in parallel for validation. G13 made two claims:

1. "Add patch: replace `git diff --quiet` with `[ -z \"$(git status --porcelain)\" ]` in `sync-backup.sh`"
2. "virtual handshake between wsl and windows and v hyper. issue"

**The agent's first instinct (this skill, hypothetically, would catch):**
quote the prior incident memory (2026-07-10 21:56, the joandrew FTP
password leak memory, which references the MSYS `git diff --quiet`
quirk), analyze the substitution, and recommend applying the patch to
`sync-backup.sh`.

**What the disk actually said:**

| Probe | Handle | Result |
|---|---|---|
| `search_files target=files pattern=sync-backup* path=/c/Users/somew` | (handle) | `{"total_count": 0}` |
| `ls ~/.hermes/scripts/` | (handle) | 28 files — no `sync-backup.sh` |
| `ls ~/.hermes/hermes-agent/scripts/` | (handle) | 25 files — no `sync-backup.sh` |
| `find /c/Users/somew -maxdepth 6 -iname "*sync*backup*"` | (handle) | Only `~/.hermes/trash/2026-07-05-1906/one-cut-deeper-sync.sh.legacy_backup` (wrong filename, in `trash/`) |

The proposed patch target did not exist. The MSYS `git diff --quiet`
analysis was technically correct in general, but **could not be applied
to a non-existent file**. The second claim ("virtual handshake between
wsl and windows and v hyper") was vague terminology with no observable
substrate:

| Probe | Handle | Result |
|---|---|---|
| `wsl -l -v` | (handle) | Only `Ubuntu` and `docker-desktop` distros, both **Stopped** |
| `docker ps` | (handle) | "failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine" — daemon not running |
| `find -iname ".wslconfig"` | (handle) | No matches |
| `find -iname "Vagrantfile"` | (handle) | No matches |
| `sqlite3 state.db "SELECT count(*) FROM sessions"` | (handle) | `0` (no recorded complaint history) |
| `grep -rli "hyper-v\|v-hyper" ~/.hermes/` | (handle, scoped) | No matches |

Both claims were **REFUTED at the existence/observation layer** before
any analysis. The empirical test of the git substitution was still
useful (it showed both commands behave identically in this minimal
test, so the specific MSYS bug couldn't be reproduced) — but the
*patch cannot be applied to a non-existent file*.

## Why this is distinct from the other anti-patterns

| Anti-pattern | What's claimed without verification |
|---|---|
| `predicting-a-cause-without-running-the-diagnostic` | "Y will fix the symptom" |
| `bug-hypothesis-before-canon-check` | "X is a NEW BUG" |
| `investigation-as-narration` | The diagnostic journey as filler |
| `claiming-credit-for-an-edit-you-didn't-make` | "I added/fixed/patched X in this session" |
| **This pattern (NEW 2026-07-11)** | **"Patch X in <file>:<line>" / "X is misconfigured in <file>" — when <file> does not exist on disk** |

The shape is: the complaint names a real-sounding target. The
complaint cites a real-sounding prior incident. The agent, primed by
the prior incident, jumps to analysis instead of verifying the target
exists. The analysis may be correct in general — but it is **correct
about a phantom artifact**, and the user's expected next step
("apply the patch") is a no-op against a non-existent file.

This is the **upstream cousin** of `predicting-a-cause-without-
running-the-diagnostic`: that anti-pattern fires when the agent
predicts a fix without running the test; this one fires when the
agent analyses a file without confirming the file is on disk.

## The operational rule (encode in SKILL.md pitfall)

**On any complaint / patch request / bug report that names a specific
file, run `ls -la <path>` / `find -iname "<basename>"` / `search_files
target=files pattern=<basename>` BEFORE writing any analysis.** If the
file does not exist:

1. **Refute the complaint at the existence layer.** Status: REFUTED,
   handle: `search_files total_count: 0` or `ls: No such file or directory`.
2. **Note the closest matches and their state** (in `trash/`?
   `legacy_backup`? named-similar but different filename? this is the
   signal that the complaint's memory is stale).
3. **Do not write a general-purpose analysis** of the proposed patch
   or fix unless the user explicitly asks. The patch is untargetable
   as stated — analysis without a target is narration.
4. **If the general advice is still useful** (e.g. "use `git status
   --porcelain` over `git diff --quiet` in future scripts"),
   state it as a one-line takeaway, not a multi-paragraph analysis.
   The user wanted a patch decision, not a lecture.

**Probe ordering when the file does not exist** (in order of cost):
1. `ls -la <direct path the complaint cites>` — single command, fastest
2. `find ~ -maxdepth 6 -iname "<basename>*"` — recursive but bounded
3. `search_files target=files pattern="<basename>*" path="<root>"` — ripgrep-backed
4. **Check the trash:** `ls ~/.hermes/trash/<most-recent-date>/` —
   the file may have been soft-deleted in a prior cleanup, and the
   complaint's memory predates the cleanup
5. **Check the legacy_backup convention:** many of the user's
   soft-deleted scripts survive as `<filename>.legacy_backup` in
   `~/.hermes/trash/<date>/`. The complaint may be about a file
   that was archived but not removed from memory.

**When the file DOES exist but is in `trash/`:** the complaint is
REFUTED for the live system but may be **true for the archived copy**.
Read the archived file, note the diff against the live system (if
any), and ask the user whether they want to revive the file or
update the complaint's memory.

**When the file does not exist anywhere** (not in `trash/`, not
`legacy_backup`, not in any mirror): the complaint is REFUTED and
**the memory that produced it is stale**. Note this explicitly in
the validation report — the user's complaint-recording pipeline
(the AI agent that issued the complaint) needs to know its
information is out of date.

## When the rule does NOT apply

- The complaint is about a **CLI command** that may or may not exist
  in the current version (use `hermes --help` / `cmd_<verb> --help`
  to verify, not a file search).
- The complaint is about a **network endpoint** (use `curl -sI` or
  a TCP probe, not a file search).
- The complaint is about a **memory record** in Mnemosyne
  (use `mnemosyne_recall` / `session_search`, not a file search).
- The complaint is about a **process / daemon** (use `process(action='list')`
  or `ps`, not a file search).

The rule fires when the complaint explicitly names a file path
**and** proposes a code/config edit. File-existence verification
is the precondition.

## User pushback phrasing that should fire this reflex

- "the file doesn't exist" (user correcting the agent mid-analysis)
- "where exactly is the file you think you're patching?"
- "you've been telling me to patch a file that isn't there for 3 turns"
- "is this complaint about a real file or did you make it up?"
- "u should validate the complaints first before recommending fixes" (2026-07-11, this user)
- "what's the actual file path, not the imagined one" (2026-07-11, this user)

**Self-tic phrases** (the agent's own narration when it's about to
analyse a phantom artifact):

- "the patch is technically correct in general"
- "the proposed fix is sound"
- "applying this to the file would address..."
- "based on the file at <path>..."  ← when <path> was never confirmed to exist
- "the prior incident memory confirms this pattern"
- "the script at <path> line <N> needs..."

When the agent's next sentence starts with one of these, the
operational reflex is: *first, run `ls` / `find` / `search_files` and
confirm the path resolves. THEN analyse.*

## Companion diagnostic recipe

The 4-handle "phantom complaint" validation report:

```bash
# Handle 1: file existence
search_files target=files pattern="<basename>*" path="<root>"
# If total_count > 0, read each match and check which is the live one
# If total_count == 0:
ls -la <direct path the complaint cites>             # confirm with single command
find ~ -maxdepth 6 -iname "<basename>*"              # recursive but bounded
ls ~/.hermes/trash/$(date +%Y-%m-%d)/               # most recent trash
ls ~/.hermes/trash/                                  # all trash dates

# Handle 2: prior session memory
# (read state.db for the complaint that named this file — if the messages
# table is empty, the complaint was issued in this session or in a prior
# session not captured in the DB)
sqlite3 ~/.hermes/state.db "SELECT count(*) FROM messages; SELECT count(*) FROM sessions;"

# Handle 3: empirical test of the proposed fix
# (when the proposed fix can be tested without the missing file, do it —
# proves whether the fix is correct in isolation, not just in theory)
cd /tmp && mkdir <test> && cd <test> && git init -q
# ... test the proposed code change ...
echo "exit=$?"

# Handle 4: WSL / VM / container substrate
wsl -l -v
docker ps 2>&1 | head -5
find ~ -maxdepth 3 -iname ".wslconfig" -o -iname "Vagrantfile"
```

**If handle 1 returns 0 matches across all probes:** the complaint is
REFUTED. State it as REFUTED, cite the 0-count handle, and stop. Do
not write a multi-paragraph analysis of the proposed fix — the
analysis has no target.

**If handle 1 returns a match in `trash/`:** the complaint may be
about a soft-deleted file. Read the archived copy, note the diff
against the live system, and ask the user whether to revive the file
or treat the complaint as moot.

**If handle 3 (empirical test) is runnable:** run it. The result is
useful even when handle 1 returns REFUTED — it tells the user whether
the proposed fix is correct in isolation, which informs the decision
to revive the file (if it should exist) or accept the phantom and
move on.

## Why "state.db is 714MB but has 0 messages" matters here

The 2026-07-11 G13 validation found a counter-intuitive state: the
`state.db` file at `~/.hermes/state.db` is **714MB** but the `messages`
and `sessions` tables both return `0` rows. The DB exists, has
`state_meta` keys (`ghost_session_prune_v1`, `orphaned_compression_finalize_v1`),
but is otherwise empty.

**What this means for complaint validation:** a complaint that cites
"prior session" or "prior incident" memory may be **citing memory
that is no longer in the DB**. The complaint-generating pipeline
(other AI agents, cron jobs, the user's own notes) may be using a
memory source other than `state.db`. The validation reflex:

1. Check `state.db` row counts first (`SELECT count(*) FROM messages;`).
2. If the complaint cites a "prior incident" with a date, look for
   that date in `state.db` AND in `~/.hermes/memories/` AND in
   `~/.hermes/trash/<date>/` AND in any `_index.json` files in trash.
3. The phantom-complaint pattern is the most common when state.db is
   empty: the AI agent that issued the complaint has **no local
   memory of the file** but was **instructed to issue a complaint
   about it** by a parent prompt or cron job. The complaint is
   often pre-scripted, not derived from observed state.

**Operational rule:** if `SELECT count(*) FROM messages` returns 0
(or any unexpectedly low number), treat the prior-session memory as
**stale or absent** and verify the complaint's cited artifacts
(file paths, line numbers, error messages) against the live system
with the 4-handle recipe above. Do not assume the complaint is
grounded in current state just because the user or a subagent
delivered it confidently.

## Cross-references

- `references/anti-pattern-predict-without-testing.md` — sibling (predicts fix without testing the fix)
- `references/anti-pattern-bug-hypothesis-before-canon-check.md` — sibling (claims NEW BUG without canon)
- `references/anti-pattern-investigation-as-narration.md` — sibling (narration over answer; this pattern's natural failure mode is to keep narrating even after the file is shown to be absent)
- `references/anti-pattern-tool-capability-invention.md` § "claiming-credit-for-an-edit-you-didn't-make" — sibling (claims authorship without verifying on disk; this pattern's mirror is "claims a file exists without verifying on disk")
- `references/503-fallback-chain-diagnostic.md` — not directly related, but the same handle-demanding discipline applies (read the log, don't speculate)
- The umbrella `hermes-windows-filesystem-ops` skill's `find`/`ls`/path discipline applies — same Windows MSYS path gotchas, just for validation probes instead of patches
