## When the work is irreversible and the right profile is unavailable (Jun 2026, this user)

When the user asks for a class of work (joandrew.com.sg, prompt engineering, model-merger, etc.) AND the current profile is the wrong one for it AND switching tabs is friction, the escape hatch is **subagent dispatch via `delegate_task`** that adopts the right profile's persona. The subagent gets a fresh context window and the right mental model.

The pattern from this user's joandrew work (Jun 2026): the user said "build the child theme, go" in `default` profile. The right profile is `communicate-design` (full site context, brand voice, FTP creds, mu-plugin rollback history). Switching tabs costs the user a context switch. The agent did the work in `default` instead — which got the work done but left the artifacts in `~/.hermes/staging/` (default's home) instead of the OCD research dir (communicate-design's home). The subagent-spawn pattern would have been:

```python
delegate_task(
    goal="Build the joandrew Direction C child theme per the plan in the parent context. 21 files. Deploy via FTP. Activate via one-shot PHP.",
    context="<full Direction C plan + child theme template structure + FTP creds + the v12.18b mu-plugin disable plan + rollback plan>",
    toolsets=["terminal", "file"],
    # adopt communicate-design's persona in the context field — no special "acp_command" needed
)
```

The subagent wouldn't have had the target profile's persistent memory (kanban state, MEMORY.md history) but would have had the right **persona** and **skills** for the work. For one-off deployments like the child theme, that's enough. For long-running work that needs persistent context across turns, the new-tab path is still better.

**The lesson:** when the user is in the wrong profile for the work they're asking for, and the work is reversible (a deploy, a code change, a config edit — all can be reverted), spawn a subagent with the right persona. Don't do the work in the wrong context AND don't ask the user to switch tabs. Ask is over-deference; doing is context-mismatch. Spawning is the right answer.
