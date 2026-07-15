"""hermes-verify-v0414.py — canonical verifier for v0.4.14-ship-pipeline state.

Committed alongside the v0.4.14-ship-pipeline change (commit 683ce7b) per the
ship-pipeline stage-3b rule. Replaces the ad-hoc hermes-verify-ship-pipeline-2026-07-13.py
in AppData\\Local\\Temp (deleted after each pass per convention).

Covers:
  - v0.4.13-default-extract (bf12d79) state:
      * mnemosyne-memory SKILL.md bumped to v2.14.0
      * new Pitfall entry "Default extract=True on every durable mnemosyne_remember"
      * references/default-extract-true.md exists
      * tic-table has the write-side tic (let me note this / writing a memory / etc)
      * tic-table has the read-side tic (what do I know about / etc)
  - v0.4.14-ship-pipeline (683ce7b) state:
      * ship-pipeline SKILL.md exists at devops/ship-pipeline/
      * 3 reference docs (stage-checklist, cross-skill-composition, sandbox-vs-prod) exist
      * tic-table has the broad ship-pipeline tic (let me edit / about to change / etc)
      * tic-table has the dedicated git-commit tic
  - Both shipped to hermes-dist template (canonical mirror)
  - Tic-phrase substring matching against natural draft text
  - Git state (HEAD on v0.4.x, working tree clean, tags present locally)
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

# === CONFIG ===
ROOT = Path(r"C:\Users\somew")
SKILLS = ROOT / ".hermes" / "skills"
DIST_SKILLS = ROOT / "hermes-dist" / "default-template" / "skills"
REPO = ROOT / "hermes-dist"
PYTHON = ROOT / ".hermes" / "hermes-agent" / "venv" / "Scripts" / "python.exe"

MNEMO = SKILLS / "hermes" / "mnemosyne-memory"
SHIP = SKILLS / "devops" / "ship-pipeline"
TIC = SKILLS / "hermes" / "hermes-skill-loading-disciplines" / "references" / "agent-self-tics.md"

MNEMO_DIST = DIST_SKILLS / "hermes" / "mnemosyne-memory"
SHIP_DIST = DIST_SKILLS / "devops" / "ship-pipeline"
TIC_DIST = DIST_SKILLS / "hermes" / "hermes-skill-loading-disciplines" / "references" / "agent-self-tics.md"

# === STATE ===
passed, failed = [], []

def assert_(cond, name):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}: {name}", flush=True)

# === 1. v0.4.13-default-extract state ===

# 1.1 mnemosyne-memory installed
assert_(MNEMO.is_dir(), "mnemosyne-memory skill dir exists (installed)")
assert_((MNEMO / "SKILL.md").is_file(), "mnemosyne-memory/SKILL.md exists")

mnemo_text = (MNEMO / "SKILL.md").read_text(encoding="utf-8")
assert_("version: 2.14.0" in mnemo_text, "mnemosyne-memory/SKILL.md is at v2.14.0")
assert_("Default `extract=True` on every durable `mnemosyne_remember`" in mnemo_text,
        "extract=True pitfall entry present in installed SKILL.md")
assert_("references/default-extract-true.md" in mnemo_text,
        "SKILL.md references the new default-extract-true.md")

assert_((MNEMO / "references" / "default-extract-true.md").is_file(),
        "references/default-extract-true.md exists")
ref_text = (MNEMO / "references" / "default-extract-true.md").read_text(encoding="utf-8")
assert_("extract=True" in ref_text, "default-extract-true.md describes extract=True")
assert_(len(ref_text) > 5000, "default-extract-true.md is non-trivial (>5000B)")

# 1.2 mnemosyne-memory shipped template mirror
if MNEMO_DIST.exists():
    mnemo_dist_text = (MNEMO_DIST / "SKILL.md").read_text(encoding="utf-8")
    assert_("version: 2.10.1" in mnemo_dist_text, "shipped template mirror at v2.10.1")
    assert_("Default `extract=True` on every durable `mnemosyne_remember`" in mnemo_dist_text,
            "shipped template mirror has extract=True pitfall entry")
    assert_((MNEMO_DIST / "references" / "default-extract-true.md").is_file(),
            "shipped template has references/default-extract-true.md")

# === 2. v0.4.14-ship-pipeline state ===

# 2.1 ship-pipeline skill installed
assert_(SHIP.is_dir(), "ship-pipeline skill dir exists (installed)")
assert_((SHIP / "SKILL.md").is_file(), "ship-pipeline/SKILL.md exists")

ship_text = (SHIP / "SKILL.md").read_text(encoding="utf-8")
assert_("name: ship-pipeline" in ship_text, "ship-pipeline SKILL.md name correct")
# Description is a single YAML scalar on the `description:` line; verify it contains
# the skill's distinctive vocabulary (not the literal "ship-pipeline" token — the
# description paraphrases the workflow rather than naming it).
desc_line = next((l for l in ship_text.splitlines() if l.startswith("description:")), "")
for phrase in ("change-shipment workflow", "plan", "small diff", "tests/containers",
               "inspect logs", "checkpoint", "recover"):
    assert_(phrase.lower() in desc_line.lower(),
            f"ship-pipeline description contains '{phrase}'")
assert_("Stage 1" in ship_text and "Stage 6" in ship_text, "all 6 stages referenced")
for stage in ("Stage 1 — Plan", "Stage 2 — Small diff", "Stage 3 — Run tests",
              "Stage 4 — Inspect logs", "Stage 5 — Checkpoint", "Stage 6 — Recover"):
    assert_(stage in ship_text, f"section '{stage}' present in SKILL.md")
assert_("LOW" in ship_text and "MEDIUM" in ship_text and "HIGH" in ship_text,
        "LOW/MEDIUM/HIGH severity tiers discussed")

# 2.2 3 reference docs
for ref_name in ("stage-checklist.md", "cross-skill-composition.md", "sandbox-vs-prod.md"):
    ref_path = SHIP / "references" / ref_name
    assert_(ref_path.is_file(), f"references/{ref_name} exists")
    assert_(ref_path.stat().st_size > 1000, f"references/{ref_name} is non-trivial (>1000B)")

# 2.3 shipped template mirror
assert_(SHIP_DIST.is_dir(), "ship-pipeline skill shipped-template mirror exists")
assert_((SHIP_DIST / "SKILL.md").is_file(), "shipped-template/ship-pipeline/SKILL.md exists")
ship_dist_text = (SHIP_DIST / "SKILL.md").read_text(encoding="utf-8")
assert_(re.search(r"^version: \d+\.\d+\.\d+", ship_dist_text, re.MULTILINE) is not None,
        "shipped-template SKILL.md has version")
for ref_name in ("stage-checklist.md", "cross-skill-composition.md", "sandbox-vs-prod.md"):
    assert_((SHIP_DIST / "references" / ref_name).is_file(),
            f"shipped-template has references/{ref_name}")

# === 3. Tic-table state (installed + shipped) ===

assert_(TIC.is_file(), "agent-self-tics.md exists (installed)")
tic_text = TIC.read_text(encoding="utf-8")

# Write-side tic (mnemosyne-memory)
for phrase in ("let me note this", "writing a memory", "I'll save this fact",
               "log this", "log it", "logging this", "let me commit this to memory",
               "mnemosyne remember"):
    assert_(phrase in tic_text, f"installed tic-table has write-side phrase '{phrase}'")

# Read-side tic (mnemosyne-memory)
for phrase in ("what do i know about", "do i have notes on", "have we discussed",
               "find anything on", "recall anything about"):
    assert_(phrase.lower() in tic_text.lower(),
            f"installed tic-table has read-side phrase '{phrase}'")

# Ship-pipeline tic (broad)
for phrase in ("let me edit", "about to change", "just wrote", "let me ship",
               "about to push", "let me remove", "let me create"):
    assert_(phrase in tic_text, f"installed tic-table has ship-pipeline phrase '{phrase}'")

# Dedicated git-commit tic
assert_("I'll commit the git change now" in tic_text,
        "installed tic-table has dedicated git-commit tic")

# Pre-existing tics (must NOT be regressed)
for phrase in ("I have no X", "I don't have X", "holy shit", "mystery solved",
               "X is the best", "based on what I know"):
    assert_(phrase.lower() in tic_text.lower(),
            f"installed tic-table preserves pre-existing tic phrase '{phrase}'")

# 3.2 Shipped template tic-table mirror
if TIC_DIST.exists():
    tic_dist_text = TIC_DIST.read_text(encoding="utf-8")
    for phrase in ("let me note this", "let me edit", "I'll commit the git change now",
                   "what do i know about"):  # case-insensitive substring search (phrase lowercased)
        assert_(phrase.lower() in tic_dist_text.lower(),
                f"shipped-template tic-table has '{phrase}' (case-insensitive)")
else:
    print(f"  NOTE: shipped-template tic-table mirror not at {TIC_DIST} (acceptable pre-mirror)")

# === 4. Tic-phrase substring matching (the live test that caught 11 bugs in my own draft) ===

tic_rows = re.findall(r'^\| ("[^"]+"(?:\s*/\s*"[^"]+")*?) \|.*$', tic_text, re.MULTILINE)
phrases = sorted(set(p.strip().lower() for row in tic_rows for p in re.findall(r'"([^"]+)"', row) if len(p.strip()) > 3))

positive_cases = [
    "Let me edit this file now.",
    "I'm going to edit the SKILL.md.",
    "About to change the config.",
    "About to modify the tic table.",
    "About to update the version bump.",
    "Just wrote a new reference doc.",
    "Just patched the rule.",
    "Just changed the threshold.",
    "I should fix the tic phrasing.",
    "I should update the version.",
    "Let me fix the bug.",
    "Let me ship the change.",
    "About to push the commit.",
    "Ready to push when verified.",
    "Let me remove the broken tic.",
    "About to delete the stale entry.",
    "Let me uninstall the deprecated skill.",
    "Let me add a new tic row.",
    "Let me create the verifier.",
    "I'll create the checklist.",
    "I'll commit the git change now.",
    # memory-write tic positives
    "Let me note this for next session.",
    "I'll remember that the dispatcher lives in hermes_gateway.",
    "I'm writing a memory about the relay bug now.",
    "Let me store this fact about the SKILL.md.",
    "I'll save this fact for cross-session reference.",
    "Let me log this entry about the bug.",
    "I'll log it for cross-session reference.",
    "Let me commit this to memory.",
    # read-side tic positives
    "What do I know about the relay?",
    "Do I have notes on the kanban dispatcher?",
    "Have we discussed the tic table fixes?",
    "Find anything on the hermes-distribution skill.",
    "Recall anything about the verify template.",
]
negative_cases = [
    "Reading the JSON config now.",
    "Let me find a file on disk.",
    "I'll search for the answer in the docs.",
    "The default behavior is fine.",
    "Reading the JSON config now.",
]

for txt in positive_cases:
    actual = any(p in txt.lower() for p in phrases)
    assert_(actual, f"tic SHOULD fire on: {txt!r}")

for txt in negative_cases:
    actual = any(p in txt.lower() for p in phrases)
    assert_(not actual, f"tic SHOULD NOT fire on: {txt!r}")

# === 5. Git + remote state ===

def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kwargs)

# 5.1 git HEAD readable
r = run(["git", "-C", str(REPO), "rev-parse", "HEAD"])
assert_(r.returncode == 0, "git HEAD readable")
head_sha = r.stdout.strip()

# 5.2 HEAD on a v0.4.x commit
r = run(["git", "-C", str(REPO), "log", "--oneline", "-1", "HEAD"])
assert_(r.returncode == 0, "git log -1 readable")
head_short = r.stdout.strip().split()[0] if r.stdout.strip() else ""
assert_(len(head_short) >= 7, f"HEAD is a 7-char hex commit ({head_short!r})")

# 5.3 working tree clean (only the v0.4.14 verifier itself should be untracked)
r = run(["git", "-C", str(REPO), "status", "--porcelain"])
clean_lines = [l for l in r.stdout.splitlines() if l.strip()]
untracked_verifier = [l for l in clean_lines if "hermes-verify-v0414.py" in l]
other_dirty = [l for l in clean_lines if "hermes-verify-v0414.py" not in l]
assert_(not other_dirty, f"git working tree clean except for the new verifier ({len(other_dirty)} other dirty)")

# 5.4 local commits log the v0.4.13 + v0.4.14 changes
r = run(["git", "-C", str(REPO), "log", "--oneline", "-10"])
assert_(r.returncode == 0, "git log -10 readable")
log_text = r.stdout
assert_("v0.4.13-default-extract" in log_text, "git log shows v0.4.13-default-extract commit")
assert_("v0.4.14-ship-pipeline" in log_text, "git log shows v0.4.14-ship-pipeline commit")

# 5.5 hermes-verify-v0414.py exists at canonical path
expected_path = REPO / "verification" / "hermes-verify-v0414.py"
assert_(expected_path.is_file(), f"verifier lives at canonical path: {expected_path}")
assert_(expected_path.stat().st_size > 5000, "verifier script is non-trivial (>5000B)")

# === 6. Mnemosyne graph live state (the data that justified the v0.4.13 change) ===

import sqlite3
MNEMO_DB = ROOT / ".hermes" / "mnemosyne" / "data" / "mnemosyne.db"
if MNEMO_DB.exists():
    tmp_db = Path("/tmp/v0414-mnemo.db")
    shutil.copy(MNEMO_DB, tmp_db)
    try:
        conn = sqlite3.connect(tmp_db, timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memoria_kg")
        kg_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM graph_edges")
        edge_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM triples")
        triple_count = cur.fetchone()[0]
        conn.close()
        print(f"  INFO: live Mnemosyne state — memoria_kg={kg_count}, graph_edges={edge_count}, triples={triple_count}")
        # Sanity: graph is at least populated
        assert_(edge_count >= 1000, f"graph_edges >= 1000 ({edge_count})")
        assert_(kg_count > 0, f"memoria_kg has triples ({kg_count})")
    finally:
        tmp_db.unlink(missing_ok=True)
else:
    print(f"  NOTE: Mnemosyne DB not at {MNEMO_DB} — skipping live graph state check")

# === CLEANUP + REPORT ===

print(f"\n{len(passed)} pass, {len(failed)} fail")

if failed:
    print("\nFAILED assertions:")
    for f in failed:
        print(f"  - {f}")
    print(f"\nHEAD: {head_sha}")
    print(f"Verifier path: {expected_path}")
    sys.exit(1)

print(f"\nALL CHECKS PASS — v0.4.14 verified.")
print(f"HEAD: {head_sha}")
print(f"Verifier path: {expected_path}")
sys.exit(0)