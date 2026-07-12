# systemd user timer template (Linux)

> **Read this when:** authoring or debugging any Hermes scheduled-job wrapper
> on Linux. Copy-paste the .service and .timer files below, substitute
> the ExecStart path, drop them under `~/.config/systemd/user/`, then
> `systemctl --user enable --now` the .timer.

## Why "user" not "system"

Two systemd scopes:
- **System** (`/etc/systemd/system/`, `/usr/lib/systemd/system/`) — runs as
  root, requires sudo. Use for OS-level services (docker, sshd).
- **User** (`~/.config/systemd/user/`) — runs as the logged-in user, no
  sudo. **This is what you want for hermes state-backup, OCD sync, and
  any user-specific scheduled work.**

User timers persist across reboots as long as the user has an active
session OR `loginctl enable-linger <user>` is set. For unattended headless
servers, run `sudo loginctl enable-linger <user>` once.

## The canonical 03:00-daily hermes-state-backup pair

### ~/.config/systemd/user/hermes-state-backup.service

```ini
[Unit]
Description=Hermes state backup (daily encrypted snapshot)
Documentation=https://hermes-agent.nousresearch.com/docs
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
# Substitute your actual hermes binary path:
ExecStart=/home/you/.hermes/hermes-agent/venv/bin/hermes state-backup
Environment="HERMES_HOME=/home/you/.hermes"
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/home/you/.hermes/hermes-agent/venv/bin"
# Stdout/stderr go to the journal by default; add logging to a file if needed:
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

### ~/.config/systemd/user/hermes-state-backup.timer

```ini
[Unit]
Description=Daily hermes state backup at 03:00

[Timer]
# 03:00:00 every day. Persistent=true = if the PC was off at 03:00,
# fire the missed run at next boot (the equivalent of Windows Task
# Scheduler's "Run task as soon as possible after a scheduled start
# is missed").
OnCalendar=*-*-* 03:00:00
Persistent=true
# Randomize delay 0-5min to avoid thundering-herd if multiple machines
# are backed up at the same cron-time:
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
```

## Install procedure

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/hermes-state-backup.service <<'SVC_EOF'
[Unit]
Description=Hermes state backup (daily encrypted snapshot)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/home/you/.hermes/hermes-agent/venv/bin/hermes state-backup
Environment="HERMES_HOME=/home/you/.hermes"
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/home/you/.hermes/hermes-agent/venv/bin"

[Install]
WantedBy=default.target
SVC_EOF

cat > ~/.config/systemd/user/hermes-state-backup.timer <<'TMR_EOF'
[Unit]
Description=Daily hermes state backup at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
TMR_EOF

# Reload to pick up the new files:
systemctl --user daemon-reload

# Enable + start the timer (enable = start on boot, --now = start now):
systemctl --user enable --now hermes-state-backup.timer

# Verify it's scheduled:
systemctl --user list-timers | grep hermes-state-backup

# Run it manually NOW to test (independent of the schedule):
systemctl --user start hermes-state-backup.service

# Check the journal for the result:
journalctl --user -u hermes-state-backup.service -n 20
```

## The 4 fields that matter (and the 4 that don't)

### Must have
- **`[Unit] Description`** — human-readable, shown in `systemctl list-timers`.
- **`[Service] ExecStart`** — absolute path to the binary + args.
- **`[Timer] OnCalendar`** — when to fire. Use `*-*-* 03:00:00` syntax
  (every day at 03:00:00).
- **`[Install] WantedBy`** — `default.target` for services that run
  on demand, `timers.target` for timers.

### Should have
- **`Persistent=true`** in the timer — without this, missed runs (when
  the PC is off at 03:00) are NOT replayed at next boot. This is the
  Linux equivalent of Windows Task Scheduler's "Run task as soon as
  possible after a scheduled start is missed". **Set this unless you
  have a reason not to.**
- **`After=network-online.target`** in the service — wait for network
  before running. Required for any backup that talks to a remote.

### Don't bother with
- **`[Service] Restart=`** — only relevant for `Type=notify` or
  `Type=forking` services. For one-shot cron-style (`Type=oneshot`),
  no restart logic needed.
- **`[Service] User=`** — `systemctl --user` already runs as the current
  user. Setting `User=` to the same user is a no-op; setting it to a
  different user requires sudo + cgroups v2 (and breaks in containers).

### Don't put in
- Comments — systemd unit files don't support comments inline (use
  `# This is a comment` syntax only as standalone lines, and the
  `;` character in some directives). Encode rationale in the commit
  message instead.

## Common Linux mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Timer scheduled but service never runs | PC not running at 03:00 AND `Persistent=false` | Set `Persistent=true` |
| Service runs but can't find `hermes` | systemd's PATH doesn't include user venv | Set `Environment="PATH=..."` |
| Service runs as wrong user | Used `systemctl` not `systemctl --user` | Always `--user` for user services |
| Timer doesn't fire on boot after power-off | `loginctl enable-linger` not set | `sudo loginctl enable-linger $USER` |
| `systemctl --user` says "Failed to connect to bus" | No active session | SSH sessions don't count; need `enable-linger` or run from a TTY |

## Quick reference: per-OS scheduler comparison

| OS | Scheduler | Config location | Load command |
|---|---|---|---|
| Windows | Task Scheduler | System → Task Scheduler (or via `schtasks`) | `schtasks /create /tn X /tr Y /sc daily /st 03:00` |
| Mac | launchd | `~/Library/LaunchAgents/com.X.plist` | `launchctl load -w ~/Library/LaunchAgents/com.X.plist` |
| Linux | systemd | `~/.config/systemd/user/X.{service,timer}` | `systemctl --user enable --now X.timer` |

All three fire at 03:00 daily. All three support "missed-run replay"
(with `Persistent=true` on systemd, `RunAtLoad=false` on launchd,
"Run task as soon as possible after a scheduled start is missed" checkbox
on Task Scheduler).