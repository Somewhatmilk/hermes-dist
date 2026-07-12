#!/usr/bin/env bash
# sanity-check.sh — quick lint for cross-platform bash scripts.
# Run before committing any new bash script under $HERMES_HOME/scripts/
# or $OCD_DIR/sync-*.sh.
#
# Usage: bash sanity-check.sh <script-path>
#
# Checks:
#   - hardcoded /c/Users/ paths (should use $_USER_DIR or $HOME)
#   - unguarded cmd //c outside OSTYPE case
#   - hermes.exe literal (should be $_HERMES_EXE_NAME)
#   - venv/Scripts/python outside Windows context
#   - unquoted heredoc markers (catches <<EOF with $VAR in template)
#   - missing set -euo pipefail
#   - direct /c/Users/somew path (PII leak — replace with $_USER_DIR)
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <script-path> [more-script-paths...]"
    exit 1
fi

EXIT_CODE=0

check() {
    local pattern="$1" description="$2" recommendation="$3"
    local matches
    matches=$(grep -nE "$pattern" "$@" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        echo
        echo "⚠️  FOUND: $description"
        echo "$matches" | head -10
        echo "   Fix: $recommendation"
        echo
        EXIT_CODE=1
    fi
}

echo "=== Cross-platform bash lint ==="
echo "Checking: $*"

# P1: hardcoded /c/Users paths
check '/c/Users/' \
    "hardcoded /c/Users/... path" \
    "Use \$_USER_DIR (derived from \$HOME + OSTYPE case)"

# P1b: hardcoded /Users (Mac) — also a host-specific leak
check '"/Users/[^"]*"' \
    "hardcoded /Users/... Mac path" \
    "Use \$_USER_DIR"

# P1c: hardcoded /home/ — Linux path leak
check '"/home/[a-z]+/' \
    "hardcoded /home/user/ Linux path" \
    "Use \$_USER_DIR"

# P2: unguarded cmd //c (outside case statement)
# Match lines with cmd //c that are NOT preceded by case/esac context.
# Heuristic: if the script has any case statement covering msys, this is
# allowed. Otherwise flag it.
check '^cmd //c ' \
    "cmd //c outside OSTYPE case" \
    "Gate to 'msys*|cygwin*) cmd //c ... ;;' inside a case statement"

# P3: literal hermes.exe
check 'hermes\.exe' \
    "literal hermes.exe in script" \
    "Use \$_HERMES_EXE_NAME (set in OSTYPE case)"

# P3b: literal hermes.exe in venv path
check 'venv/Scripts/hermes' \
    "literal venv/Scripts/ path" \
    "Use \$_HERMES_EXE_SUBDIR/\$_HERMES_EXE_NAME"

# P4: literal venv/Scripts/python on Mac/Linux
# Hard to detect without AST, but flag the obvious case.
check 'venv/Scripts/python[^ ]*' \
    "literal venv/Scripts/python path" \
    "Use \$_HERMES_VENV_BIN which is OSTYPE-aware"

# P5: tilde in env defaults (not expanded)
check ':="\${?[A-Z_]*}:=~' \
    "tilde (~) in env default — won't expand under set -u" \
    "Use \$HOME or \$_USER_DIR instead"

# P6: missing set -euo pipefail
FIRST_LINE=$(head -1 "$1" || true)
if ! grep -q '^set -euo pipefail' "$@"; then
    echo
    echo "⚠️  MISSING: 'set -euo pipefail' (or stricter) — unhandled errors will pass silently"
    echo "   Fix: add 'set -euo pipefail' as the second line (after shebang)"
    echo
    EXIT_CODE=1
fi

# P7: heredoc with $VAR in unquoted delimiter (likely mistake)
# Heuristic: any <<EOF (unquoted) followed by a line containing literal $ that
# doesn't look like a real env interpolation. False positive rate is high
# but the warning is worth surfacing.
check '<<EOF$' \
    "unquoted heredoc <<EOF (no single-quote delimiter)" \
    "If you don't want shell interpolation, use <<'EOF' instead"

# P11 (NEW 2026-07-03): profile-sync without lsp/browser_screenshots/cache exclusion
for script in "$@"; do
    if grep -q '\$PROFILES_SRC' "$script" 2>/dev/null; then
        if ! grep -q 'lsp/node_modules' "$script" 2>/dev/null; then
            echo
            echo "⚠️  P11: $script walks \$PROFILES_SRC without lsp/node_modules exclusion"
            echo "   Add '-not -path \"*/lsp/node_modules/*\"' to the find filter."
            echo
            EXIT_CODE=1
        fi
    fi
done

# P13 (NEW 2026-07-03): hardcoded AppData/Local/hermes instead of $_USER_DIR/.hermes
check 'AppData/Local/hermes' \
    "hardcoded AppData/Local/hermes path" \
    "Use \$_USER_DIR/.hermes (works on Windows MSYS + Mac/Linux)"

# P14 (NEW 2026-07-03): git pull --rebase + git rm -r without dirty-tree guard
for script in "$@"; do
    if grep -q 'git pull.*--rebase\|git pull origin' "$script" 2>/dev/null; then
        if grep -q 'git rm -r ' "$script" 2>/dev/null; then
            echo
            echo "⚠️  P14: $script does 'git pull ... --rebase' and 'git rm -r'"
            echo "   Use 'git pull --ff-only' or 'git fetch' instead."
            echo
            EXIT_CODE=1
        fi
    fi
done

# P15 (NEW 2026-07-11): bash heredoc + python "$path" arg passed MSYS form.
# Catches the pattern:  "$PY" - "$SOME_PATH" <<'PYEOF'  where $SOME_PATH is
# a bash-expanded path. On Windows, bash happily works with the MSYS form,
# but native Windows python can't read "/c/..." — it needs "C:\\...".
# If the script defines a *_NATIVE / to_native_path helper, it has been
# taught the rule; otherwise flag once.
for script in "$@"; do
    if grep -nE '"\$PY"\s+-\s+"\$' "$script" 2>/dev/null | head -1 >/dev/null \
       || grep -nE '(python|python3)\s+-\s+"\$' "$script" 2>/dev/null | head -1 >/dev/null; then
        if ! grep -qE 'to_native_path|_NATIVE\s*=|cygpath -w' "$script" 2>/dev/null; then
            echo
            echo "⚠️  P15: $script invokes python with \"\$VAR\" path but has no native-path helper"
            echo "   On Windows, native python can't read MSYS paths (\"/c/...\")."
            echo "   Define to_native_path() and pass \$(to_native_path \"\$VAR\") to python."
            echo "   Reference: cross-platform-bash-scripting SKILL.md, pitfall P15."
            echo
            EXIT_CODE=1
        fi
    fi
done

# Summary
echo
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "✅ Clean: no obvious cross-platform issues found."
else
    echo "❌ Issues found. Fix above before committing."
fi

exit $EXIT_CODE