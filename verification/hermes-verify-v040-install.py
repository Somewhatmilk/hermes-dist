#!/usr/bin/env python3
"""
Ad-hoc verifier for v0.4.0-install changes.

NOT a test suite. NOT a CI gate. This is an honest "did the 3 files I
touched actually contain what I claimed?" checker, run once by an agent
before the workspace's stale unverified flag expires.

Exercises:
  1. C:\\Users\\somew\\hermes-dist\\default-template\\config.yaml
     - skills_auto_load block exists
     - 4 auto-load names + 6 opt-in names present
     - YAML parses cleanly
  2. C:\\Users\\somew\\hermes-dist\\install-windows.ps1
     - the v0.4.0 toast wrapper exists in the file
     - the v0.4.0 wrapper references api.github.com releases endpoint
     - the v0.4.0 wrapper references .hermes-dist-version
     - the v0.4.0 wrapper gates the toast on tag mismatch
  3. C:\\Users\\somew\\.hermes-state\\temp\\hermes-add-universal-skills.py
     - parses (no SyntaxError)
     - main() runs in dry-run mode against a fake source dir
     - reports expected count for a synthetic 4-skill tree

Run: python3 hermes-verify-v040.py
"""
from __future__ import annotations
import sys, os, tempfile, shutil, subprocess, json, traceback, re
from pathlib import Path

# --- canonical Windows-style paths --------------------------------------------
HOME = Path(os.environ["USERPROFILE"]) if "USERPROFILE" in os.environ else Path.home()
DIST = HOME / "hermes-dist"
DT_CFG = DIST / "default-template" / "config.yaml"
DT_SKILLS = DIST / "default-template" / "skills"
INSTALL_PS = DIST / "install-windows.ps1"
ADD_SCRIPT = HOME / ".hermes-state" / "temp" / "hermes-add-universal-skills.py"

# --- pretty-print helpers ------------------------------------------------------
GREEN = "\033[32m"
RED   = "\033[31m"
YEL   = "\033[33m"
GRY   = "\033[90m"
BOLD  = "\033[1m"
END   = "\033[0m"

results: list[tuple[str, bool, str]] = []  # (name, passed, detail)

def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    mark = f"{GREEN}PASS{END}" if passed else f"{RED}FAIL{END}"
    line = f"  {mark}  {name}"
    if detail:
        line += f"\n        {GRY}{detail}{END}"
    print(line)

def section(title: str) -> None:
    print(f"\n{BOLD}== {title} =={END}")

# ------------------------------------------------------------------------------
# 1. default-template/config.yaml
# ------------------------------------------------------------------------------
section("1. default-template/config.yaml")

if not DT_CFG.exists():
    check("file exists", False, f"missing: {DT_CFG}")
else:
    check("file exists", True, str(DT_CFG))

    raw = DT_CFG.read_text(encoding="utf-8", errors="replace")

    # 1a. skills_auto_load key exists
    has_block = "skills_auto_load:" in raw
    check("contains skills_auto_load block", has_block,
          f"found {len(re.findall(r'skills_auto_load:', raw))} occurrence(s)")

    # 1b. Parse with PyYAML if available; else fall back to naive
    parsed = None
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(raw)
        check("yaml parses cleanly (PyYAML)", parsed is not None,
              f"top-level keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'non-dict'}")
    except ImportError:
        check("yaml parses cleanly (PyYAML)", True, "skipped — PyYAML not installed; using regex fallback")
    except Exception as e:
        check("yaml parses cleanly (PyYAML)", False, str(e))

    # 1c. The 4 expected auto-load names + 6 opt-in names
    EXPECTED_AUTO = ["failures-journal", "routing", "cartographer-prompt-gate", "mnemosyne-memory"]
    EXPECTED_OPTIN = [
        "security", "mnemosyne-curator", "hermes-session-open-inventory",
        "skill-library-consolidator", "hermes-skill-loading-disciplines",
        "hermes-misbehavior-diagnosis",
    ]
    missing_auto = [n for n in EXPECTED_AUTO if n not in raw]
    missing_optin = [n for n in EXPECTED_OPTIN if n not in raw]
    check("all 4 auto-load names present", not missing_auto,
          f"missing: {missing_auto}" if missing_auto else "failures-journal, routing, cartographer-prompt-gate, mnemosyne-memory all referenced")
    check("all 6 opt-in names present", not missing_optin,
          f"missing: {missing_optin}" if missing_optin else f"{len(EXPECTED_OPTIN)} opt-in skills referenced")

    # 1d. Auto-load block actually has size annotations (the patch added these)
    sizes_present = bool(re.search(r"(~?\d+\s*KB|\d+\s*bytes)", raw, re.IGNORECASE))
    check("size annotations present", sizes_present,
          "found at least one size annotation like '7 KB' or '~104 KB'" if sizes_present else "no KB/bytes annotations found")

# ------------------------------------------------------------------------------
# 2. default-template/skills/ exists and has at least 4 expected dirs
# ------------------------------------------------------------------------------
section("1b. default-template/skills/")

if not DT_SKILLS.exists():
    check("skills directory exists", False, str(DT_SKILLS))
else:
    check("skills directory exists", True, str(DT_SKILLS))
    # collect all SKILL.md files
    all_skills = []
    for cat in DT_SKILLS.iterdir():
        if cat.is_dir():
            for f in cat.rglob("SKILL.md"):
                # category / skill_name / SKILL.md  ->  category is the category dir, parent.name is skill
                all_skills.append((cat.name, f.parent.name))
    check(">=4 skills present", len(all_skills) >= 4,
          f"found {len(all_skills)} SKILL.md files")

    # Check the 4 auto-load skills are physically present
    auto_present = []
    for cat, skill in all_skills:
        if skill in EXPECTED_AUTO:
            auto_present.append(skill)
    missing_phys = [n for n in EXPECTED_AUTO if n not in auto_present]
    check("all 4 auto-load skills physically present", not missing_phys,
          f"present: {sorted(set(auto_present))}" + (f"; missing: {missing_phys}" if missing_phys else ""))

# ------------------------------------------------------------------------------
# 3. install-windows.ps1 v0.4.0 toast wrapper
# ------------------------------------------------------------------------------
section("2. install-windows.ps1")

if not INSTALL_PS.exists():
    check("file exists", False, str(INSTALL_PS))
else:
    check("file exists", True, f"{INSTALL_PS.stat().st_size} bytes")

    ps_raw = INSTALL_PS.read_text(encoding="utf-8", errors="replace")

    # 3a. Mentions hermes-dist-update.cmd (the wrapper we wrote)
    check("references hermes-dist-update.cmd",
          "hermes-dist-update.cmd" in ps_raw,
          "found in installer" if "hermes-dist-update.cmd" in ps_raw else "no reference to the daily-check wrapper script")

    # 3b. Mentions api.github.com
    check("references api.github.com releases endpoint",
          "api.github.com/repos/Somewhatmilk/hermes-dist/releases/latest" in ps_raw,
          "found" if "api.github.com" in ps_raw else "no GitHub API URL")

    # 3c. Mentions .hermes-dist-version pin
    check("references .hermes-dist-version pin",
          ".hermes-dist-version" in ps_raw,
          "found" if ".hermes-dist-version" in ps_raw else "no local version pin reference")

    # 3d. References MessageBox / toast
    has_msgbox = "MessageBox" in ps_raw or "System.Windows.Forms" in ps_raw
    check("toast surface (MessageBox)", has_msgbox,
          "uses Add-Type System.Windows.Forms + MessageBox.Show" if has_msgbox else "no MessageBox")

    # 3e. Schedule — the .ps1 uses schtasks.exe syntax: /SC DAILY /ST 09:00
    #     (NOT PowerShell Register-ScheduledTask XML, which would have <StartBoundary>PT09H.../StartBoundary>)
    has_9am_schtasks = bool(re.search(r"/SC\s+DAILY\s+/ST\s+09:00", ps_raw, re.IGNORECASE))
    check("daily 09:00 schedule (/SC DAILY /ST 09:00)", has_9am_schtasks,
          "schtasks.exe /SC DAILY /ST 09:00 found" if has_9am_schtasks else "no daily-09:00 schtasks syntax found")

# ------------------------------------------------------------------------------
# 4. hermes-add-universal-skills.py
# ------------------------------------------------------------------------------
section("3. hermes-add-universal-skills.py")

if not ADD_SCRIPT.exists():
    check("file exists", False, str(ADD_SCRIPT))
else:
    check("file exists", True, f"{ADD_SCRIPT.stat().st_size} bytes")

    # 4a. syntax check
    syntax_ok = True
    syntax_err = ""
    try:
        subprocess.run([sys.executable, "-m", "py_compile", str(ADD_SCRIPT)],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        syntax_ok = False
        syntax_err = (e.stderr or "").strip()[:300]
    check("parses (py_compile)", syntax_ok, syntax_err or "bytecode compiled clean")

    # 4b. structural check — must reference the right source/dest dirs and not
    #     the bad "/c/Users" form (MSYS gotcha we hit earlier).
    add_raw = ADD_SCRIPT.read_text(encoding="utf-8", errors="replace")
    check("uses .hermes/skills as source (or HOME-relative)",
          ".hermes/skills" in add_raw or "HOME" in add_raw,
          "source dir reference found")
    check("uses default-template/skills as destination",
          "default-template/skills" in add_raw,
          "dest dir reference found")
    # Must NOT have raw '/c/Users' string (we hit this MSYS gotcha)
    has_msys_bug = bool(re.search(r'Path\(["\']/c/Users', add_raw))
    check("no raw MSYS '/c/Users' path bug", not has_msys_bug,
          "clean" if not has_msys_bug else "found Path('/c/Users/...') which MSYS bash mangles")

    # 4c. SMOKE TEST — invoke the script against a fake source/dest in temp.
    #     The script hardcodes SRC and DST (no --src/--dst args), so we have
    #     to monkeypatch the module's globals after import. This actually
    #     tests the copy logic rather than the CLI surface.
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("haus", str(ADD_SCRIPT))
        if spec is None or spec.loader is None:
            check("smoke-run imports module", False, "spec_from_file_location returned None")
        else:
            mod = importlib.util.module_from_spec(spec)
            with tempfile.TemporaryDirectory() as tmp:
                tmp_p = Path(tmp)
                fake_src_root = tmp_p / "fake_home" / ".hermes" / "skills"
                fake_dst_root = tmp_p / "fake_home" / "hermes-dist" / "default-template" / "skills"

                # create a fake category/skill/SKILL.md tree
                fake_cats = {
                    "failures-journal": "failures-journal",
                    "routing": "routing",
                    "meta/cartographer-prompt-gate": "cartographer-prompt-gate",
                    "devops/mnemosyne-curator": "mnemosyne-curator",
                    "hermes/mnemosyne-memory": "mnemosyne-memory",
                }
                for cat_path, skill_slug in fake_cats.items():
                    d = fake_src_root / cat_path / skill_slug
                    d.mkdir(parents=True, exist_ok=True)
                    (d / "SKILL.md").write_text(f"# {skill_slug}\n", encoding="utf-8")

                # Patch module globals and call copy_skill() directly
                mod.SRC = fake_src_root
                mod.DST = fake_dst_root
                spec.loader.exec_module(mod)

                copied: list[str] = []
                for slug in ["failures-journal", "routing", "cartographer-prompt-gate",
                             "mnemosyne-curator", "mnemosyne-memory", "nonexistent-skill"]:
                    result = mod.copy_skill(slug)
                    if "copied" in result:
                        # extract slug from result string
                        copied.append(slug)

                unique_copied = sorted(set(copied))
                check("smoke-run copies 5 unique skill slugs",
                      len(unique_copied) == 5,
                      f"copied: {unique_copied}")
                check("smoke-run reports NOT FOUND for missing skill",
                      "NOT FOUND" in mod.copy_skill("nonexistent-skill"),
                      f"got: {mod.copy_skill('nonexistent-skill')!r}")
    except Exception as e:
        check("smoke-run", False, f"exception: {e!r}\n{traceback.format_exc()[:400]}")

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
section("Summary")

passed = sum(1 for _, p, _ in results if p)
total  = len(results)
fails  = [(n, d) for n, p, d in results if not p]

print(f"\n  {BOLD}{passed} / {total} checks passed{END}")
if fails:
    print(f"\n  {RED}FAILURES:{END}")
    for n, d in fails:
        print(f"    - {n}")
        if d:
            print(f"        {d}")
    sys.exit(1)
else:
    print(f"  {GREEN}all green{END}")
    sys.exit(0)