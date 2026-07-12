# hermes-dist skill shipment 2026-07-12

**Purpose:** durable, single-file record of the v0.4.0 / v0.4.1 / v0.4.2 skill-shipment work, written because conversation-history consolidation drops the detail and Mnemosyne recall is unreliable for this kind of dense context. Read this in any future session to recover the full picture.

**Scope:** all 3 commits pushed to `Somewhatmilk/hermes-dist` today (2026-07-12), with reasoning, file lists, and what's still pending.

**Authored:** 2026-07-12 (during session that shipped v0.4.2-skills, in response to the consolidation-failure-mode observation).

---

## TL;DR

| Tag | Commit | What | Auto-load | Opt-in | Total skills shipped |
|---|---|---|---|---|---|
| `v0.4.0-design` | `de66e3a` | heartbeat → user-initiated `hermes update-dist`, 10 universal skills | 4 | 6 | 10 |
| `v0.4.0-install` | `70f7db6` | daily 09:00 `hermes-dist-update.cmd` (Windows only) | — | — | — |
| `v0.4.1-skills` | `0dd8581` | 6 new opt-in skills + mnemosyne-memory Mental Model | 4 | 12 | 16 |
| `v0.4.2-skills` | `0b0c8b9` | cross-session-todo-handoff opt-in skill | 4 | 13 | 17 |

**Auto-load set: 4 skills (~104 KB system-prompt cost, unchanged from v0.4.0).** No new auto-loads — every addition has been opt-in to keep first-message latency stable.

---

## v0.4.0-design (`de66e3a`)

**Why:** user explicitly said "i dont need a heartbeat to monitor and change the soul.md when i never agree to a push, automatically i rather have control over a pushed version. Only when a new version appear on git will the user side be prompted for a update."

**What changed:**
- Removed T3 60s push-heartbeat (the `/api/v1/profile-bundle` poll)
- Added user-initiated `hermes update-dist` flow
- On hermes launch / daily scheduled task, installer queries `https://api.github.com/repos/Somewhatmilk/hermes-dist/releases/latest`
- If newer than `~/.hermes/profiles/<uuid>/.hermes-dist-version`, a toast prompts the user
- User runs `hermes update-dist` to see the diff and approve (no auto-apply, no auto-download)

**Universal skills shipped (10):**
- Auto-load (4, ~104 KB system-prompt cost): `failures-journal`, `routing`, `cartographer-prompt-gate`, `mnemosyne-memory`
- Opt-in (6, ~270 KB surface, only loads when user runs `hermes skills install <slug>`): `security`, `mnemosyne-curator`, `hermes-session-open-inventory`, `skill-library-consolidator`, `hermes-skill-loading-disciplines`, `hermes-misbehavior-diagnosis`

**Skill-selection reasoning:** top-25 skills ranked by mention-count across all 21 local session JSON files. Top-10 picked for shipping. The 4 smallest-and-highest-impact went to auto-load; the other 6 shipped but opt-in. The decision criterion: "would a user who knows nothing about my workflow benefit from this?"

---

## v0.4.0-install (`70f7db6`)

**Why:** the v0.4.0 design needs an actual installer that wires the daily-check + toast. Without this, the design is just docs.

**What changed:**
- `install-windows.ps1` now generates a `hermes-dist-update.cmd` registered as a Windows Task Scheduler task running daily at 09:00
- The .cmd does: `git pull --ff-only` (silent) → `GET api.github.com/repos/Somewhatmilk/hermes-dist/releases/latest` → compare tag → show `MessageBox` toast if newer
- Powershell MessageBox via `Add-Type -AssemblyName System.Windows.Forms` + `MessageBox.Show`

**Important asymmetry:** only Windows installer is at v0.4.0/v0.4.1 parity. `install-linux.sh` and `install-macos.sh` are still at v0.3.0. They need:
- Linux: systemd user timer (`~/.config/systemd/user/hermes-dist-update.timer`) + `notify-send` from `libnotify-bin`
- macOS: launchd plist at `~/Library/LaunchAgents/com.hermes.dist.update.plist` + `osascript -e 'display notification "..." with title "hermes-dist"'`

**Why deferred:** user explicitly chose Windows-first during v0.4.0 design. Estimated effort to bring to parity: ~2 hours total.

---

## v0.4.1-skills (`0dd8581`)

**Why:** user asked for 4 areas of skill coverage — webscraping, principles, memory mental model, QoLs — and approved Option A for all 4.

**What changed:**

**Webscraping (1 skill):**
- `web-interaction` (12 KB, SKILL.md only) — Firecrawl / web_extract / Playwright selection matrix. References directory NOT shipped (236 KB → 12 KB) so users can opt in to the references separately.

**QoLs (2 skills):**
- `background-process-lifecycle` (36 KB, full with references/scripts) — daemon/watcher lifecycle, session_id discipline, `notify_on_complete` vs `watch_patterns` decision matrix, MSYS-detach trap
- `cross-platform-bash-scripting` (84 KB, full) — OSTYPE-aware bash, cron/launchd/systemd/Task-Scheduler dispatch, MSYS path-bridge, CPython→bash subprocess path bridge

**Principles (3 NEW skills, all in `prompt-engineering/`):**
- `prompt-direction-format-examples` (6 KB) — the 5-step prompt ladder (Direction → Format → Examples → Evaluate → Divide-Labor)
- `diagnose-root-cause` (5 KB) — patch the cause, not the symptom
- `socratic-prompting` (6 KB) — 3-questions pattern before strategic work (real goal / missing constraints / smallest version)

**Memory mental model (1 in-place patch):**
- `mnemosyne-memory` SKILL.md got a new "Mental Model" section at the top (read-first before the API surface). 5 mental-model points: (1) recall returns relevant-not-correct, (2) the four surfaces are not interchangeable, (3) memory layers not types, (4) importance+recency+similarity is ranking not authority, (5) this is the agent's notebook not the user's browsing surface. File size 33 KB → 36 KB.

**Configuration changes:**
- `default-template/config.yaml` opt-in catalog updated to 12 skills (~430 KB surface)
- `SHIP.md` got a v0.4.1-skills section

**NO new auto-load skills.** System-prompt cost stays at ~104 KB.

**Honest caveats about the 3 NEW principles:**
- Written from your r/PromptEngineering canon memory, not battle-tested
- I synthesized the prompts from the canon, not your verbatim wording
- If after dogfood you find them off-base, edit the SKILL.md directly (plain markdown, no compile)

---

## v0.4.2-skills (`0b0c8b9`)

**Why:** user identified a cross-session memory failure mode — "in another session I should have addressed the Linux/macOS issue. If so how can u do better cross memory between each session harmoniously?" — and asked me to ship a skill for it.

**The failure mode the skill addresses:** Mnemosyne handles recall well for *facts* but doesn't have a first-class "open work" concept. Open work is stateful + open-ended + has not-yet-done-ness. A new session can recall facts but has no signal that something is IN-PROGRESS unless the agent explicitly writes a high-importance dated note.

**The fix:**
- Use a canonical Mnemosyne slot (`work.in_progress`) as the source-of-truth for what's in progress
- Write the slot at session end, plus a high-importance dated `mnemosyne_remember` call
- Read both at session start, before answering the user's query
- Designed to be sleep-resistant: importance ≥0.85 + `valid_until` ~1 month

**The skill: `cross-session-todo-handoff` (10 KB, opt-in)**
- Located at `~/.hermes/skills/meta/cross-session-todo-handoff/SKILL.md`
- Also copied to `default-template/skills/meta/cross-session-todo-handoff/SKILL.md` for distribution
- Provides: `handoff.read` ritual (session start), `handoff.write` ritual (session end or pivot), worked example, 5 anti-patterns, configuration knobs

**Why canonical slot + remember, not just one:** canonical slot is structured and queryable but doesn't surface in temporal recall; remember is recall-ranked but lossy. Write both, read both.

**Configuration changes:**
- `default-template/config.yaml` opt-in catalog: 12 → 13 skills (~430 → ~440 KB)
- `SHIP.md` got a v0.4.2 section
- mnemosyne call already made: `mnemosyne_remember(importance=0.85, valid_until=2026-09-12)` capturing the v0.4.2 deferral

---

## What's still pending (open work, future sessions)

**From the v0.4.2 handoff note (memory ID `d6f1b93bba1b3df2`):**

1. **Linux/macOS installer parity** — `install-linux.sh` + `install-macos.sh` at v0.3.0; need daily-update toast (notify-send + osascript). Estimated effort: ~2 hours. Explicitly deferred at v0.4.0 design time.
2. **`default-template/mcps/` starter compose-yamls** — ComfyUI, filesystem, database templates. No user request yet.
3. **`default-template/SKILLS.md` index file** — list all 17 shipped skills with descriptions. No user request yet.
4. **Investigate `$TMP=/tmp/skill-mentions3.txt` env bug** — root cause of broken interactive `git push` and PowerShell `Add-Type` errors. Worked around but not fixed.

**From the Tailscale GUI investigation (2026-07-11):**

- Tailscale GUI is broken on operator's Windows PC. Diagnosed: stale UWP AppUserModelID registration `{6D809377-6AF0-444B-8957-A3773F02200E}` pointing at non-existent Store-version path. Cannot fix from agent. User-side fix: `tailscale web` (works), or MSI reinstall of Tailscale, or manual registry cleanup. Relay at `100.106.125.105:9119` is fine; the daemon is up; only the GUI frontend is broken.

---

## Repository state (as of v0.4.2)

- **Local:** `C:\Users\somew\hermes-dist\` on commit `0b0c8b9`, working tree clean
- **Remote:** `0b0c8b9` + tag `v0.4.2-skills` on `Somewhatmilk/hermes-dist`
- **Tags on remote (7):** `v0.1.0`, `v0.2.1`, `v0.2.2`, `v0.3.0`, `v0.4.0-design`, `v0.4.0-install`, `v0.4.1-skills`, `v0.4.2-skills`
- **Relay:** live at `100.106.125.105:9119` (Tailscale CGNAT, not public)
- **Sandbox:** `~/hermes-dist-test/` verified end-to-end (16/16 self-test + 3 audit events shipped to relay with HTTP 200, all HMAC-verified)
- **Skills in default-template/:** 17 (4 auto + 13 opt-in)
- **Auto-load system-prompt cost:** ~104 KB (unchanged from v0.4.0)

---

## Honest caveats across all 3 commits

- **The 3 principle skills in v0.4.1 are new, written from your r/PromptEngineering canon memory, not battle-tested.** If you find them off-base, edit SKILL.md directly.
- **The Mental Model section in `mnemosyne-memory` is my synthesis, not your canon wording.**
- **`web-interaction` references/ (200 KB) are deliberately NOT shipped.** The user-facing experience is "see the trigger index, pull references on demand."
- **No second-machine end-to-end test.** The dogfood sandbox was on the same machine as the operator. Cross-Tailscale-peer install not verified.
- **No CI gate.** All verification was ad-hoc, single-pass, with verifier scripts deleted after each run.
- **The verifier scripts are not in the repo (except the v0.4.0 one at `verification/hermes-verify-v040-install.py`).** To re-verify v0.4.1 or v0.4.2, re-create from this conversation or `git log -p` the commits.

---

## How to recover from consolidation in future sessions

1. **Read this file first** if you're picking up a hermes-dist conversation after a context break.
2. **Check Mnemosyne canonical slot** `work.in_progress` via `mnemosyne_recall_canonical(category="work", name="in_progress")`. Update it at session end via `mnemosyne_remember_canonical`.
3. **For procedural memory** (how to do X, decision trees, anti-patterns), read the SKILL.md files directly: `read_file(C:\Users\somew\hermes-dist\default-template\skills\...SKILL.md)`.
4. **For git history** of what was committed when, use `git log --oneline` in `C:\Users\somew\hermes-dist\`.
5. **For the actual shipped content** (canonical truth), read SHIP.md and the SKILL.md files. Don't trust Mnemosyne recall alone.

---

**File location:** `C:\Users\somew\.hermes\sessions\2026-07-12-hermes-dist-skill-shipment.md`
**Last updated:** 2026-07-12 (during v0.4.2 verification cycle)
**Reliable until:** 2026-09-12 (mirror of v0.4.2 mnemosyne valid_until)