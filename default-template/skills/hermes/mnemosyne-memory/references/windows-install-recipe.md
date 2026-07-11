# Mnemosyne Windows Install Recipe

Reproducible install recipe for `mnemosyne-memory 3.10.0` + `mnemosyne-hermes 0.2.0` on Windows with the Hermes agent venv. Captures the 4 gotchas the official install script can't handle silently. Use this when `pip install mnemosyne-hermes` succeeds but `hermes memory status` shows the plugin as not detected.

## Prerequisites

- Python 3.10+ in the hermes-agent venv at `C:\Users\<user>\AppData\Local\hermes\hermes-agent\venv\`
- `HERMES_HOME` env var pointing at the actual hermes config dir (typically `C:\Users\<user>\AppData\Local\hermes`)
- Admin NOT required if you follow the copy-not-symlink path below

## Step 1 — install pip packages

```powershell
& "$env:HERMES_HOME\hermes-agent\venv\Scripts\python.exe" -m pip install mnemosyne-memory mnemosyne-hermes
```

This installs `mnemosyne-memory 3.10.0` (core SQLite + recall) and `mnemosyne-hermes 0.2.0` (the hermes plugin adapter). Entry points register automatically:
- `hermes_agent.memory_providers: mnemosyne = mnemosyne_hermes`
- `hermes_agent.plugins: mnemosyne = mnemosyne_hermes:register`

The pip install alone is NOT enough — hermes uses its own plugin discovery (`plugins.memory.discover_memory_providers`) that scans `$HERMES_HOME/plugins/<name>/` directories, not entry points. So you also need step 2.

## Step 2 — copy plugin to user plugins dir

The official `mnemosyne-hermes install` command tries to symlink `$HERMES_HOME/plugins/mnemosyne/` to the pip package. On Windows, non-admin users get `WinError 1314` on `os.symlink`. Workaround: copy instead.

```powershell
$src = "$env:HERMES_HOME\hermes-agent\venv\Lib\site-packages\mnemosyne_hermes"
$dst = "$env:HERMES_HOME\plugins\mnemosyne"

# Remove any stale install (e.g. an old github clone)
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }

# Full copy
robocopy $src $dst /E /NFL /NDL /NJH /NJS /NP
```

Verify:
```powershell
Get-ChildItem $dst
# Expect: __init__.py (88,706 bytes), audit.py, cli.py, hermes_llm_adapter.py, install.py, plugin.yaml, sync_adapter.py, tools.py, upgrade.py
```

## Step 3 — patch the eager `from mnemosyne.core...` import

Open `$dst\__init__.py`. Line 31 contains:
```python
from mnemosyne.core.episodic_graph import GraphEdge
```

This is an **eager** module-level import. When hermes loads the plugin via `plugins.memory.discover_memory_providers`, it puts `plugins/mnemosyne/__init__.py` on a synthetic package path `_hermes_user_memory.mnemosyne`. Python's import system then finds THIS `__init__.py` first when resolving `import mnemosyne` (from inside this very file's eager import). But this `__init__.py` doesn't have a `core` submodule — so the import fails with `ModuleNotFoundError: No module named 'mnemosyne.core'`.

Replace the eager import with a deferred function:
```python
# OLD (line 31):
# from mnemosyne.core.episodic_graph import GraphEdge

# NEW:
def _get_graph_edge():
    import mnemosyne.core.episodic_graph as _ge
    return _ge.GraphEdge
```

Then find and update every usage. Search for `GraphEdge` in the file and wrap each usage:
```python
# OLD: GraphEdge(...)
# NEW: _get_graph_edge()(...)
```

This forces python to do the import at call time, when `mnemosyne.core.episodic_graph` is on sys.path via site-packages (not blocked by the outer plugin wrapper).

## Step 4 — configure hermes

Edit `$HERMES_HOME\config.yaml`:
```yaml
memory:
  provider: mnemosyne
  memory_enabled: false        # disable built-in MEMORY.md
user_profile_enabled: false    # disable USER.md
```

That's the entire swap from built-in memory to mnemosyne. Two flags.

## Step 5 — verify

```powershell
hermes memory status
```

Expected output (truncated):
```
Memory status
────────────────────────────────────────
  Built-in:  always active
  Provider:  mnemosyne

  Plugin:    installed ✓
  Status:    available ✓

  Installed plugins:
    • mnemosyne  (local) ← active
```

If `Plugin` shows NOT installed but the file copy + patch are in place, check:
1. `__init__.py` exists at `$env:HERMES_HOME\plugins\mnemosyne\__init__.py` (~2.6 KB after patch)
2. The patch removed the line-31 eager import
3. `$env:HERMES_HOME\plugins\mnemosyne\plugin.yaml` exists (it has metadata hermes reads)

## End-to-end smoke test

```powershell
& "$env:HERMES_HOME\hermes-agent\venv\Scripts\mnemosyne.exe" store "windows install verified $(Get-Date -Format yyyy-MM-dd)" "install-recipe" 0.7

& "$env:HERMES_HOME\hermes-agent\venv\Scripts\mnemosyne.exe" recall "windows install" 3
```

Should return 1+ results with the test fact in the output.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'mnemosyne.core'` | line-31 eager import not patched | re-apply step 3 |
| `Plugin: NOT installed` in `hermes memory status` | plugin copy missing or wrong dir | re-apply step 2 |
| `RecursionError` on plugin load | outer wrapper calling itself via spec_from_file_location | use line-31 patch only, don't wrap in a lazy-loading wrapper |
| `WinError 1314` during install | trying to symlink without admin | use robocopy per step 2 |
| `mnemosyne.exe: Unknown command` | the package wasn't installed in the venv the CLI was launched from | re-install per step 1 |

## Undo (revert to built-in memory)

```powershell
# Remove plugin
Remove-Item "$env:HERMES_HOME\plugins\mnemosyne" -Recurse -Force

# Edit config back to built-in
# (in $env:HERMES_HOME\config.yaml)
# memory:
#   memory_enabled: true
# user_profile_enabled: true
# (remove the provider line)

# Restart hermes
hermes gateway restart

# Optionally uninstall packages
& "$env:HERMES_HOME\hermes-agent\venv\Scripts\python.exe" -m pip uninstall mnemosyne-memory mnemosyne-hermes -y
```

The mnemosyne SQLite DB at `$env:HERMES_HOME\mnemosyne\data\mnemosyne.db` is NOT removed by this — export first with `mnemosyne export backup.json` if you want to preserve.
