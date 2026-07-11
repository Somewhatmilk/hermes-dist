## Profile clone trap — `cp -r profiles/X profiles/Y` makes Y a wrong-scope copy (Jun 2026, this user)

If you (or the user) creates a new profile by copying another profile's directory:

```bash
cp -r ~/.hermes/profiles/communicate-design ~/.hermes/profiles/marketing-seo
```

The new profile starts with a **verbatim clone** of the source's `SOUL.md`, `MEMORY.md`, `skills/` directory, and `memories/` directory. Hermes One does not detect this — the profile loads, the skills install, but the agent operates with the **source's field scope, not the new field's scope**. Real example 2026-06-25: `marketing-seo` was created as a clone of `communicate-design`. The agent answered Airbnb/STR queries with WP/SEO framing because that's what the cloned SOUL.md was tuned for. The user caught it: "i dont get why we have a duplicate."

**Right pattern when creating a profile:**
1. **Regenerate `SOUL.md` from scratch.** Don't copy.
2. **Audit the cloned `MEMORY.md`** — it will reference projects from the source profile.
3. **Audit the cloned `skills/`** — drop skills that don't apply to the new field.
4. **Verify with `hermes profile list` and `hermes profile show <name>`** — the field scope is in the SOUL.md, not the directory name.

**Better pattern (this user's preferred): don't create a profile at all — fit the work into an existing field-profile per the bigger-field rule.** The `marketing-seo` clone would never have existed if STR/Airbnb work was put under `communicate-design` from the start. Per the rule above ("one profile per FIELD, all projects in that field"), STR/Airbnb IS a child process of communication design — listing optimization is content/SEO + design. The 2026-06-25 fix was: delete the `marketing-seo` clone, merge STR work into `communicate-design` (including the `airbnb-listing-optimizer` skill, which was correctly scoped in marketing-seo, and the `airbnb-and-str-context.md` memory file). The bigger-field rule beats the "I need a separate profile" reflex.
