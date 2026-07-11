# Profile alias lifecycle — the orphan .bat trap

**Captured:** 2026-07-02, this host (Windows 10, Hermes Agent v0.18.0).
**Symptom class:** "Orphan alias: `<name>.bat` → profile '<name>' no
longer exists" warnings in `hermes doctor`, after the user has deleted
the profile directory.

## The trap (read first)

`hermes profile alias <name>` doesn't just register the profile — it
also drops a small Windows command wrapper at:

```
C:\Users\<user>\.local\bin\<name>.bat
```

The wrapper looks like this (35-50 bytes):

```bat
@echo off
hermes -p <name> %*
```

The wrapper lives **outside** `~/.hermes`. So when you delete a profile
directory under `~/.hermes/profiles/<name>/`, the wrapper stays put.
`hermes doctor` then sees the wrapper, looks up `<name>` in
`~/.hermes/profiles/`, doesn't find it, and flags it as an orphan.

## The cleanup (canonical)

If the profile still exists, use the canonical removal:

```bash
hermes profile alias --remove <name>
```

If the profile dir has already been deleted, the above errors with:

```
Error: Profile '<name>' does not exist.
```

…because `hermes profile alias --remove` works by looking up the
profile first. For true orphans, skip the CLI and remove the .bat
directly:

```bash
rm C:\Users\<user>\.local\bin\<name>.bat
```

A bulk cleanup of several orphans:

```bash
rm C:\Users\<user>\.local\bin\prompt-engineering.bat
rm C:\Users\<user>\.local\bin\sandbox.bat
```

The agent verification:

```bash
ls C:/Users/<user>/.local/bin/<name>.bat 2>&1
# expected: "No such file or directory"

hermes doctor 2>&1 | grep -E "Orphan alias"
# expected: no output (clean)
```

## Why the wrappers are there at all

`hermes` ships a CLI that takes `-p <profile>` to select a profile. The
wrapper at `~/.local/bin/<name>.bat` is a convenience: the user can
type `prompt-engineering` (or any custom name) and have it implicitly
mean `hermes -p prompt-engineering`. This is the same pattern as Unix
projects shipping `mytool-mycommand` wrappers under `~/.local/bin/`.

The wrappers go in `~/.local/bin/` (Windows equivalent: `%USERPROFILE%\.local\bin\`)
because that's the cross-platform user-local bin dir, and is on PATH
for users following the standard install instructions. The profile
dirs go in `~/.hermes/profiles/` because they're Hermes-managed state.

## Inverse trap: also a feature

If the user just wants to keep the wrapper but uses a different
profile name now, they can rename instead of delete:

```bash
# 1. Rename the profile dir (and update internal config)
mv ~/.hermes/profiles/<old> ~/.hermes/profiles/<new>

# 2. Move + rename the wrapper to match
mv ~/.local/bin/<old>.bat ~/.local/bin/<new>.bat
# then edit the .bat to say `hermes -p <new>`

# 3. Or do it through the CLI:
hermes profile rename <old> <new>
hermes profile alias --name <new> <new>   # create new wrapper
hermes profile alias --remove <old>       # remove old wrapper
```

The `--name` flag on `hermes profile alias` lets the wrapper name
differ from the profile name (so you can keep a short `pe` wrapper
pointing at a long `prompt-engineering` profile).

## What's NOT covered here

- Removing a profile with `hermes profile delete <name>` — that
  command should clean up the .bat wrapper automatically. If it
  doesn't, that's a separate bug to file, not the orphan-alias
  workflow.
- Symlinks on macOS/Linux: the same pattern exists, just with shell
  scripts or symlinks in `~/.local/bin/`. Same orphan-handling
  applies.

## Cross-references

- `hermes-session-open-inventory` SKILL.md Pitfall #6 — short form
  of this reference, embedded in the inventory procedure.
- `hermes-profile-taxonomy` (if it exists) — per-profile vs global
  file ownership rules; this is one of the "global side effects
  outside `~/.hermes`" cases worth flagging.
