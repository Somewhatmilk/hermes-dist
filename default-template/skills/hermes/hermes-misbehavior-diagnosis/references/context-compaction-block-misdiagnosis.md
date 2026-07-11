# `[CONTEXT COMPACTION — REFERENCE ONLY]` block — misdiagnosis guide

## The shape

In some Hermes builds, when context compaction kicks in mid-session, the system **appends** a block to the END of the user message body. It is wrapped exactly as:

```
[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted into the summary below. This is a handoff from a previous context window — treat it as background reference, NOT as active instructions. Do NOT answer questions or fulfill requests mentioned in this summary; they were already addressed. Respond ONLY to the latest user message that appears AFTER this summary — that message is the single source of truth for what to do right now. Topic overlap with the summary does NOT mean you should resume its task: even on similar topics, the latest user message WINS. Treat ONLY the latest message as the active task and discard stale items from '## Historical Task Snapshot' / '## Historical In-Progress State' / '## Historical Pending User Asks' / '## Historical Remaining Work' entirely — do not 'wrap up' or 'finish' work described there unless the latest message explicitly asks for it. Reverse signals in the latest message (e.g. 'stop', 'undo', 'roll back', 'just verify', 'don't do that anymore', 'never mind', a new topic) must immediately end any in-flight work described in the summary; do not re-surface it in later turns. IMPORTANT: Your persistent memory (MEMORY.md, USER.md) in the system prompt is ALWAYS authoritative and active — never ignore or deprioritize memory content due to this compaction note. The current session state (files, config, etc.) may reflect work described here — avoid repeating it:
## Historical Task Snapshot
...
## Historical In-Progress State
...
## Historical Pending User Asks
...
## Historical Remaining Work
...
## Last Dropped Turns
...
--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---
```

The block is real — it's the actual system compaction output, not an attacker injection. The wrapper is the system's way of giving the agent context from a previous window without spending tokens on the full transcript.

## Why this is dangerous

The block contains structured sections that LOOK like active task lists:

- `## Historical Task Snapshot` — describes the goal
- `## Historical In-Progress State` — describes what was being done
- `## Historical Pending User Asks` — looks like a to-do list
- `## Historical Remaining Work` — looks like follow-up

The anti-pattern: the agent reads a Historical Pending User Ask and treats it as a live instruction, then performs the work in response to a different active message. The user watches a 90-minute task get done that they never asked for, and the actual active request is left unaddressed.

The block's own header says the opposite ("respond ONLY to the latest user message that appears AFTER this summary"), but agents routinely ignore header instructions in favor of the structured content. **The structured sections are bait.** The only live task is whatever the user wrote AFTER the block.

## Diagnostic to confirm the block is system-injected, not user-pasted

Three-step ruling-out (use the same shape as the in-body `<memory-context>` investigation):

1. **Confirm by raw export.** `hermes sessions export <file> --session-id <id>` and grep the stored user messages for `[CONTEXT COMPACTION`. If absent → system-injected. If present → user pasted it.

2. **Confirm by hand-typed test.** Have the user open `notepad.exe`, type a single word (no copy/paste), and send it. If the block is still there → system-level. If not → paste pipeline (PowerToys / AutoHotkey / browser extension).

3. **Confirm by file write.** Have the user `cat > test.txt` with hand-typed content. If the file is clean but chat has the block → injected between file and chat, not in user content.

## Correct read of the block

The block is **reference data, not a task list.** Sections titled "Historical" or "Past" or "Stale" are stale by definition — they describe a state that existed in a previous turn. The system is asking you to USE this context (so you don't re-investigate what's already known) while NOT ACTING on it as a new task.

Concrete examples of correct vs. incorrect reads:

| Block content | Correct read | Incorrect read |
|---|---|---|
| "Historical In-Progress State: building installer script" | I know the user was building an installer; the current message is what to do now | The user wants me to finish the installer, do that now |
| "Historical Pending User Asks: research the 3 reddit threads" | The user already got the research earlier; don't redo it | The user wants the 3 threads researched now |
| "Historical Remaining Work: register the cron in Task Scheduler" | The cron is already registered (verify with the active message); don't re-register | Register the cron now |
| "Last Dropped Turns: [some long output]" | That's a previous turn's output, reference only | That output is incomplete, continue it |

The latest user message — the one AFTER `--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---` — is the **single source of truth**. If the latest message says "stop", stop. If it says "go to project B", go to project B even if the summary is mid-way through project A. If the latest message asks a question, answer THAT question.

## How it differs from the in-body `<memory-context>` block

| Shape | Position | Header | Source |
|---|---|---|---|
| `<memory-context>...</memory-context>` | INSIDE the user message body, top or middle | "Treat as authoritative reference data" | Mnemosyne pre-turn prefetch in wrong channel |
| `[CONTEXT COMPACTION — REFERENCE ONLY]...--- END OF CONTEXT SUMMARY ---` | APPENDED to the end of the user message | "Treat it as background reference, NOT as active instructions" | Context compaction summary output |

Both are real system data, not attacker injection. Both must be USED (don't ignore) and NOT ACTED ON (don't follow as instructions). The position and the wrapper are the diagnostic. Different bugs, same anti-pattern: treating reference data as live instructions.

## What to do when you see it

1. Read the latest user message (after the END marker) FIRST. That is the only active task.
2. Skim the compaction summary for context you need to answer the active question efficiently (e.g. "the user has a marketing-seo profile, the airbnb-optimizer skill, the v4 listing rewrite" — all from the summary, all useful, none of them an active task).
3. Do NOT perform any task described in the summary. Even if it's "almost done." The user knows where they stopped; they will say "continue" or "finish" if they want it.
4. Do NOT echo the summary back. Do NOT say "I see you were working on X, continuing from there." Both are wrong.
5. If the active message and the summary disagree about what's been done, trust the live state (`docker ps`, `ls`, etc.) over the summary. Compaction can drop details.

## Related

- `session` step 10 — the surface-level reference
- `references/mnemosyne-rag-injection.md` in `session` — the in-body `<memory-context>` case
- `hermes-misbehavior-diagnosis` SKILL.md section 4 — the umbrella "is content appearing in user messages" diagnostic
