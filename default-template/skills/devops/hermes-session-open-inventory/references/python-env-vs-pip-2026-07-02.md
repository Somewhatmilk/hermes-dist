# Python-env vs pip alignment — the hidden venv split

**Captured:** 2026-07-02, this host (Windows 10, Hermes Agent v0.18.0).
**Symptom class:** "Plugin is installed but Status: not available" in
`hermes memory status`, with `No module named '<pkg>'` from
`hermes <plugin> doctor`.

## The trap (read first)

`hermes` runs inside its own venv. The `pip` on your PATH may be bound
to a *different* venv. When you `pip install <pkg>`, the package lands
in whichever venv `pip` belongs to — NOT necessarily the one Hermes
will import from. `hermes` finds the plugin's on-disk directory
(✓ installed) but cannot import the package into its own interpreter
(✗ not available). The user sees a confusing state where every
verification surface — pip exit code, doctor message, memory status —
looks slightly different.

## The diagnostic (3 commands, ~5 seconds)

```bash
# 1. Which Python does hermes run under?
hermes --version
# Look at the 'Python:' line and the binary path:
#   $ where hermes   →  C:\Users\<user>\.hermes\hermes-agent\venv\Scripts\hermes.exe
#   $ hermes --version → Python: 3.11.15

# 2. Is the pip on PATH in the same venv?
$ which pip
$ pip --version
#   pip 24.0 from C:\Users\<user>\llama.cpp\env\Lib\site-packages\pip (python 3.11)
# ↑ WRONG. Different venv.

# 3. Install through Hermes's venv explicitly:
$ C:\Users\<user>\.hermes\hermes-agent\venv\Scripts\python.exe -m pip install <pkg>
# Note: bash on Windows mangles '.exe' suffixes, so prefer:
$ /c/Users/<user>/.hermes/hermes-agent/venv/Scripts/python.exe -m pip install <pkg>
```

## The verification ritual (after install)

Don't trust the pip exit code. Verify the import works *from the
interpreter Hermes actually uses*:

```bash
$ /c/Users/<user>/.hermes/hermes-agent/venv/Scripts/python.exe -c \
    "from <pkg>.<known_symbol> import <Thing>; print('OK')"
```

A successful core import means the install actually landed in the right
place. Anything else means you're still in the wrong venv.

## The placeholder-shadow anti-pattern

A second failure mode that compounds the venv-split problem: the
package name you type into `pip install` may resolve to a small
**placeholder** package on PyPI that has the right top-level name but
no useful modules. For the Hermes mnemosyne plugin:

| `pip install ...`                  | Wheel size | What you get                              |
|------------------------------------|------------|-------------------------------------------|
| `mnemosyne`                        | 5.1 kB     | Placeholder stub; `mnemosyne.core` is a dir but `beam` module absent. Shadow of the real package's namespace. |
| `mnemosyne-hermes`                 | 8 MB+      | Real plugin + `mnemosyne-memory` 3.11.1 as transitive dep. Has `mnemosyne.core.beam`, `mnemosyne.core.memory`, etc. |

**Heuristic:** if `pip install <pkg>` produced a wheel under ~50 kB and
the import still fails with `No module named '<pkg>.<x>'`, you almost
certainly installed a placeholder. The real package will be obvious in
size (a 3.11.x library pulls in numpy, sqlite-vec, fastembed, etc. —
hundreds of MB total).

**For the mnemosyne plugin specifically:** the docstring at the top of
`~/.hermes/plugins/mnemosyne/__init__.py` says:

> Install: `pip install mnemosyne-hermes`
> Then set in `~/.hermes/config.yaml`: `memory.provider: mnemosyne`

And the `plugin.yaml` is `name: hermes-mnemosyne, version: 0.2.0`. If
the docstring and plugin.yaml exist, follow them — don't guess.

## Why "active plugin" listings are misleading

`hermes memory status` lists `Plugin: installed ✓` for every plugin it
finds on disk in `~/.hermes/plugins/<name>/`. That's a **plugin
presence** check, not a **runtime import health** check. The actual
runtime health is the separate `Status:` line, which is set by calling
`is_available()` on the loaded provider. A plugin can be `installed ✓`
and `not available ✗` simultaneously — that's the "everything is on
disk but nothing imports" state. Always read both lines.

## Worked transcript (2026-07-02, this host)

```
$ where hermes
C:\Users\somew\.hermes\hermes-agent\venv\Scripts\hermes.exe

$ hermes --version
Hermes Agent v0.18.0  ·  Python: 3.11.15

$ which pip
/c/Users/somew/llama.cpp/env/Scripts/pip          ← wrong venv

$ /c/Users/somew/.hermes/hermes-agent/venv/Scripts/python.exe -m pip install mnemosyne
Collecting mnemosyne
  Downloading mnemosyne-0.1.0-py3-none-any.whl (5.1 kB)   ← placeholder!
Successfully installed mnemosyne-0.1.0

$ hermes mnemosyne doctor
Error: Mnemosyne not available: No module named 'mnemosyne.core.beam';
       'mnemosyne.core' is not a package

$ /c/Users/somew/.hermes/hermes-agent/venv/Scripts/python.exe -m pip uninstall -y mnemosyne
$ /c/Users/somew/.hermes/hermes-agent/venv/Scripts/python.exe -m pip install mnemosyne-hermes
Installing collected packages: ..., mnemosyne-memory-3.11.1, mnemosyne-hermes-0.3.1, ...
Successfully installed ...

$ hermes mnemosyne doctor
Mnemosyne Diagnostics
  Checks passed: 11/31
  Semantic search is active with 120 vectors in episodic memory (backend: int8)
  Working-memory sqlite-vec coverage complete

$ hermes memory status
  Plugin:    installed ✓
  Status:    available ✓      ← now green
```

## The general pattern (any plugin, any language)

Whenever a plugin uses a language runtime with multiple venvs / toolchains
(Python venvs, Node nvm versions, Ruby rbenv, etc.), the install command
must be issued through the venv the **host application** uses, not the
one the user's shell defaults to. The diagnostic chain is the same:

1. Find the host's runtime: `where <host>` / `<host> --version`
2. Find the install tool's runtime: `which <install_tool>` / `<install_tool> --version`
3. If they differ, install through the host's runtime explicitly
4. Verify with a known-symbol import, not the install tool's exit code

## Cross-references

- `hermes-session-open-inventory` SKILL.md Step 2.5 — the inventory
  procedure that bakes this check in at session start.
- `hermes-misbehavior-diagnosis` — detective counterpart when a plugin
  fails at runtime; the venv-split is the most common "phantom" cause.
- `hermes-windows-filesystem-ops` — same verification discipline
  applied to file landings.
