# launchd plist template (Mac)

> **Read this when:** authoring or debugging any Hermes scheduled-job wrapper
> on macOS. Copy-paste the plist below, substitute the label and program
> path, write it to `~/Library/LaunchAgents/com.<label>.plist`, then
> `launchctl load -w` it.

## The canonical 03:00-daily hermes-state-backup LaunchAgent

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Label: reverse-DNS-style unique identifier. Convention: com.<user>.<task> -->
    <key>Label</key>
    <string>com.user.hermes-state-backup</string>

    <!-- ProgramArguments: argv to pass. Hermes CLI takes a subcommand. -->
    <key>ProgramArguments</key>
    <array>
        <string>/Users/somew/.hermes/hermes-agent/venv/bin/hermes</string>
        <string>state-backup</string>
    </array>

    <!-- EnvironmentVariables: PATH is critical (Mac's launchd PATH is
         /usr/bin:/bin:/usr/sbin:/sbin — no /usr/local/bin, /opt/homebrew/bin). -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HERMES_HOME</key>
        <string>/Users/somew/.hermes</string>
    </dict>

    <!-- StartCalendarInterval: fire at 03:00 every day. -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <!-- StandardOutPath / StandardErrorPath: where logs go.
         The dir must exist or launchd will refuse to start the agent. -->
    <key>StandardOutPath</key>
    <string>/Users/somew/.hermes/logs/state-backup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/somew/.hermes/logs/state-backup.err</string>

    <!-- RunAtLoad: false = don't fire on launchctl load. true = fire immediately
         on load (useful for one-shot migrations, NOT for daily backups). -->
    <key>RunAtLoad</key>
    <false/>

    <!-- Nice: lower priority so the backup doesn't fight interactive work.
         10 = low priority. -->
    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
```

## Install procedure

```bash
mkdir -p ~/Library/LaunchAgents
mkdir -p ~/.hermes/logs

# Substitute your actual path before writing:
cat > ~/Library/LaunchAgents/com.user.hermes-state-backup.plist <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.user.hermes-state-backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.hermes/hermes-agent/venv/bin/hermes</string>
        <string>state-backup</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HERMES_HOME</key><string>$HOME/.hermes</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/.hermes/logs/state-backup.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.hermes/logs/state-backup.err</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST_EOF

# Validate the plist parses (catches typos before launchctl does):
plutil -lint ~/Library/LaunchAgents/com.user.hermes-state-backup.plist

# Register it. -w means "load even if disabled by default" (overrides
# the disabled flag if launchd had it disabled).
launchctl load -w ~/Library/LaunchAgents/com.user.hermes-state-backup.plist

# Verify it's loaded:
launchctl list | grep com.user.hermes-state-backup
```

## The 6 fields that matter (and the 4 that don't)

### Must have
- **`Label`** — unique ID, reverse-DNS-style.
- **`ProgramArguments`** — array, argv. First element = absolute path to
  the executable. **Must be absolute; tilde doesn't work in plists.**
- **`StartCalendarInterval`** OR **`StartInterval`** OR **`RunAtLoad`** —
  pick one trigger.
- **`StandardOutPath`** / **`StandardErrorPath`** — capture logs. The dir
  must exist or launchd fails silently.

### Should have
- **`EnvironmentVariables`** — at minimum `PATH`. launchd's default PATH
  is `/usr/bin:/bin:/usr/sbin:/sbin`, missing `/usr/local/bin` (Homebrew
  Intel) and `/opt/homebrew/bin` (Homebrew Apple Silicon). **This is the
  #1 cause of "launchd job runs but command not found" on Mac.**

### Don't bother with
- `KeepAlive`, `RunAtLoad: true` (only for one-shot migrations, not daily).
- `UserName` — only relevant for system LaunchDaemons; you're writing a
  per-user LaunchAgent so it runs as the logged-in user anyway.

### Don't put in
- Comments — plist is XML, no comment syntax. Encode the rationale in
  the file's commit message instead.

## Common Mac mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `launchctl load` succeeds but job never runs | `ProgramArguments` uses `~` | Use absolute path (`/Users/you/...`) |
| Job runs but `command not found` in logs | launchd's PATH doesn't include Homebrew dirs | Add `PATH` to `EnvironmentVariables` |
| Job runs but can't read `$HOME/.hermes/` | `HERMES_HOME` env var unset | Add `HERMES_HOME` to `EnvironmentVariables` |
| `plutil -lint` fails with parse error | Unquoted `&` or `<` in a string | XML-escape: `&amp;`, `&lt;` |
| Job fires twice at 03:00 | Both `StartCalendarInterval` and `StartInterval` set | Pick one |
| Logs say "service already loaded" | `launchctl load` after previous `launchctl unload` race | Use `launchctl bootout`/`bootstrap` on modern launchd |

## Updating an existing plist

To re-register a plist after editing it (without rebooting):

```bash
# Unload + load the same file:
launchctl unload ~/Library/LaunchAgents/com.user.hermes-state-backup.plist
launchctl load -w ~/Library/LaunchAgents/com.user.hermes-state-backup.plist

# Verify:
launchctl list | grep com.user.hermes-state-backup
```

The `-w` flag is essential — without it launchd will silently skip the load
if the job was previously disabled.