## Kanban CLI gotchas (NEW 2026-06-27, this session)

Burned 3 iterations to learn these. Future agent creating kanban tickets will hit the same wall. Full session detail in `references/kanban-cli-gotchas.md`. Quick version:

- **`hermes kanban create` does NOT accept `--title`.** Title is positional: `hermes kanban create "My title" --body "..."`. `--title` is silently rejected with `error: unrecognized arguments: --title`.
- **`--board <slug>` is a subcommand flag on `hermes kanban`, not a global `hermes` flag.** Either pass it after the subcommand (`hermes kanban --board foo create ...`) or run `hermes kanban boards switch foo` first. Passing `--board` before the subcommand gets `error: argument command: invalid choice: 'foo'`.
- **Do NOT pass `--skill` flags on a ticket.** The kanban dispatcher validates `--skill` against the **dispatching profile's** skill catalog, not the target assignee's. So `--skill my-skill` from default to communicate-design fails with `Error: Unknown skill(s): my-skill` even if communicate-design has it. The fix is: write the skill request into the ticket BODY, not the flag. (Captured 2026-06-27 20:43, t_7b1d7a2f failure.)
- **`hermes kanban create --json` returns the full task object including the new `id`.** Use this for scripted flows where you need to claim/assign/link the new ticket. Without `--json`, output is human-readable and harder to parse.

- **MSYS single-quote trap (NEW 2026-07-11).** When invoking `hermes kanban create --body "..."` from an MSYS bash heredoc, user-input text containing apostrophes (`it's`, `don't`, `what's`) silently breaks the shell parser. Two fixes: (a) escape via `'\''` inside double quotes (POSIX idiom), or (b) write a Python seed script and execute via `python.exe script.py` — preferred when the body is >5 lines or contains nested quotes. Bash timeout + unterminated-quote errors look like the agent is broken; they're really the shell giving up on the parse.

- **Direct SQLite seeding when CLI is hostile (NEW 2026-07-11, this session).** When the CLI form of `hermes kanban create` is fighting you (wrong flag position, MSYS path quoting, body with embedded quotes, etc.), drop to direct SQLite. Pattern:
  ```python
  # ~/.hermes/kanban/boards/<slug>/kanban.db
  import sqlite3, secrets, time
  conn = sqlite3.connect(r'C:\Users\somew\.hermes\kanban\boards\<slug>\kanban.db')
  cur = conn.cursor()
  task_id = 't_' + secrets.token_hex(4)  # matches kanban_db.py generator
  cur.execute("""
      INSERT INTO tasks (id, title, created_at, status, assignee, priority, body)
      VALUES (?, ?, ?, ?, ?, ?, ?)
  """, (task_id, TITLE, int(time.time()), 'triage', 'default', 9, BODY))
  conn.commit()
  ```
  Always PRAGMA the schema first (`SELECT name FROM sqlite_master WHERE type='table'` then `PRAGMA table_info(tasks)`) to discover the exact column names — they vary by kanban-db version. Read back via `SELECT id, title, status, assignee, priority FROM tasks` to confirm. This is the **fallback** path — prefer the CLI when it cooperates because it triggers any dispatch-side hooks/init that direct SQLite bypasses.

- **Board naming: project name, not topology (NEW 2026-07-11, this user correction).** When creating a kanban board for a project, name the slug after the PROJECT NAME (e.g. `hermes-dist`), not the topology/feature (e.g. `tailscale`). Project boards outlive topology pivots — the user pivoted the topology from Oracle Cloud to Tailscale mid-session, but the project name `hermes-dist` stayed the same. Topology-specific work can live as columns or ticket prefixes (`T1 — relay dry-run`); the board identity stays stable. Pitfall I hit: named the board `tailscale` first, then realized the project name should win. Rename is `hermes kanban boards rename <slug> <new-name>` (display name only) but the slug is immutable — to truly rename the slug, dump + recreate.

**Full session detail:** `references/kanban-cli-gotchas.md` — covers `--title` rejection, `--board` subcommand-vs-global flag confusion, `--skill` flag antipattern, `--json` for scripts, priority-as-int, multi-line body via `$(cat file)`, and the post-create verification recipe. Read before your first `hermes kanban create` of the session.
