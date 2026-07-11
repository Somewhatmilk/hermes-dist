## Profile switch vs subagent-as-profile (NEW 2026-06-27, user correction)

There are TWO distinct operations that the agent can confuse:

1. **SESSION-LEVEL profile switch** = `hermes --profile <name>` from the command line = different SOUL.md, MEMORY.md, skills/, system prompt, all of it. **Cannot do mid-conversation** — you have to exit the current session and start a new one.

2. **SUBAGENT-AS-PROFILE** = `delegate_task` with a `context` field that includes the target profile's SOUL.md + skill list + relevant memory, telling the leaf "you are the <profile-name> profile, here's your toolkit, do this work." **CAN do mid-conversation.**

The mechanism is the same as any parallel research subagent dispatch. The agent has the right tool (`delegate_task`) and should use it.

**Wrong framing the agent fell into (2026-06-27):** "I can't switch profiles so I'll just do the work in default." That's wrong on two counts:
- It's the wrong profile for the work (rules/skills/memory mismatch)
- The subagent-as-profile path was available the whole time

**Right framing:** "I can't switch profiles (session-level), but I CAN spawn a subagent with the right profile's persona. That's what I'll do." The subagent gets a fresh context window with the target profile's skills in its `context` field, and the work happens in that context.

**Rule:** when the user asks for profile-specific work and you're in the wrong session, **dispatch a subagent with the target profile's context as its setup, NOT "I can't switch profiles"** and definitely NOT "I'll just do it here anyway."

The subagent's `delegate_task` is disabled (max_spawn_depth=1) so no recursive spawning. Trade-off: the subagent has the right *persona* and *skills* for the work but lacks the target profile's *persistent memory* and *persistent kanban state*. For verification / code review / iteration work, this is enough. For long-running work that needs persistent context across turns, the new-tab path is still better.
