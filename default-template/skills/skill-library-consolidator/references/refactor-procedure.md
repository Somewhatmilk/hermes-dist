## The Refactor Procedure

Seven steps. Each ends with a checkable completion criterion. Don't skip
verification — `write_file` is silent on whether the refactor improved
anything.

### Step 1 — Inventory and pick the target

If the user named the file, use it. Otherwise pick the **top-N largest**
plain-text `.md` in the catalog:

```bash
# Hermes-home tree (active)
find ~/.hermes/skills -name SKILL.md -printf '%s %p\n' | sort -rn | head -10

# Same for SOUL.md, AGENTS.md, INDEX.md, README.md
find ~/.hermes -maxdepth 4 \( -name 'SOUL.md' -o -name 'AGENTS.md' \
   -o -name 'INDEX.md' -o -name 'README.md' \) -printf '%s %p\n' | sort -rn | head -10
```

Sort by size; the largest are the highest-leverage wins. Threshold for
"worth refactoring": over 20 KB. Below that, the skill is probably already
in good shape.

**Completion criterion:** a concrete list of files with their current byte
counts. No vague "look at the big ones" — name each file and its size.

### Step 2 — Read the file end-to-end

Open the whole file. Use `read_file` (paginate if >500 lines), not
`head`/`tail` — the end and middle are where sediment lives. Read it
**looking for these patterns** and tag every match with `L<line>`:

| Pattern | Tag | What it means |
|---|---|---|
| Same rule stated twice | `DUP` | Duplication |
| "Be careful / be thorough / use best practices" | `NOOP` | No-op prose |
| `description:` over 400 chars | `DESC` | Frontmatter drift |
| Date stamp in body (`Self-audit 2026-…`, `Updated YYYY-MM-DD`) | `DATE` | Sediment |
| A command/path that hasn't been re-verified | `STALE` | Sediment risk |
| A key-shaped string (sk-, ghp_, AKIA, long base64) | `LEAK` | Secret leak — flag immediately |
| Section header with no body under it | `EMPTY` | Dead heading |
| Reference to a file that doesn't exist | `BROKEN` | Dangling link |
| Sentence that uses "I" / "we" / "let's" as if teaching a human | `TONE` | Wrong audience (the skill talks to the model, not the user) |
| `## Examples` with one example or copy-pasted from another skill | `BLOAT` | Section is paying for nothing |

**Completion criterion:** every match above is recorded with `L<line>` and
the tag. Output as a markdown table or a `grep -n` style list. The list is
the refactor plan.

### Step 3 — Classify: keep / cut / fold / move

For every tagged line from Step 2, choose one of:

- **KEEP** — the rule genuinely changes model behavior. Stay.
- **CUT** — dead weight. Delete the sentence, the section, the example.
- **FOLD** — duplicates an existing rule elsewhere in the same file.
  Delete the weaker copy; keep one canonical location. Cite the kept
  line in the deletion note.
- **MOVE** — bulky reference that doesn't need to be loaded on every
  `skill_view`. Move to `references/<file>.md` in the same skill dir;
  reference it from SKILL.md with `See references/foo.md for …`.
- **FIX (frontmatter only)** — `description:` is too long or missing the
  "Use when …" trigger shape. Rewrite; never delete.

**Hard rules during classification:**

- Don't keep two copies "for clarity." The second one is the wrong one.
- Don't move a rule to `references/` just to make the byte count lower.
  If the rule is on the hot path (always needed when the skill loads),
  it stays in SKILL.md.
- Don't refactor the frontmatter `description:` mid-body. The validator
  enforces ≤1024 chars; peers sit at 150-300.
- Don't add new section headers when an existing one already covers the
  rule. (This is the user's load-bearing rule — `hermes-agent-skill-authoring`
  SKILL.md lists it as pitfall #11.)

**Completion criterion:** every tagged line has a classification. No
"maybe" or "TBD" — those become CUT.

### Step 4 — Apply via `patch` (preferred) or `write_file` (rewrite)

- **Targeted edits** (cut one sentence, fold a duplicate, fix the
  description): use `patch(mode='replace', old_string=…, new_string=…)`.
  Match a unique snippet; include enough surrounding context to be unique.
- **Major rewrites** (over ~30% of file changes): use `write_file`. Read
  the current content first, then write the new whole.

Never use `sed`/`awk` in terminal — the `patch` tool is the right
primitive, and the auto-syntax-check on `.md` after write catches broken
frontmatter.

**Pitfall — patch failure loops.** If a `patch` fails twice on the same
snippet (whitespace drift, surrounding context changed), switch to
`write_file` for the enclosing section. Don't loop.

**Completion criterion:** the file is rewritten; `head -3` shows valid
`---\nname: …\ndescription: …` frontmatter; byte count is meaningfully
lower (target: ≥30% reduction on files >20 KB).

### Step 5 — Verify frontmatter and content

```python
import yaml, re, pathlib
content = pathlib.Path("<path>").read_text(encoding="utf-8")
assert content.startswith("---\n"), "frontmatter not at byte 0"
m = re.search(r'\n---\s*\n', content[3:])
fm = yaml.safe_load(content[3:m.start()+3])
assert "name" in fm and "description" in fm
assert len(fm["description"]) <= 1024, f"description too long: {len(fm['description'])}"
assert len(content) <= 100_000, f"file too big: {len(content)}"
# Smoke-test: name from frontmatter matches directory slug
assert pathlib.Path("<path>").parent.name == fm["name"], "name/dir mismatch"
print("OK", len(content), "bytes")
```

Run that snippet via `terminal` with the active Python (see "Same venv"
below). It catches:

- Lost leading `---`
- Frontmatter closed with wrong separator
- `name:` missing or not matching directory
- `description:` over the validator's 1024-char limit
- File over the validator's 100 KB ceiling

**Completion criterion:** the script prints `OK <bytes>`. If any assert
fires, fix and re-run before declaring done.

### Step 6 — Cross-reference check

After the rewrite:

- `related_skills:` still resolves to skills that exist in the catalog.
  Run `skills_list` once after a session reset to verify; in this
  session, run `search_files(target='files', pattern='<name>')` against
  `~/.hermes/skills/`.
- Any `See references/<file>.md` pointer still resolves. Verify with
  `ls <skill-dir>/references/`.
- Any URL in the body — quick `web_search` not needed unless the URL is
  load-bearing; for in-repo skills the docs URL is fine as-is.

**Completion criterion:** every external reference resolves. If a
`related_skills:` entry points to a removed skill, either delete the
entry or create the missing skill — don't leave dangling references.

### Step 7 — Report concrete metrics

Always end with a **before / after table**:

| Metric | Before | After | Δ |
|---|---|---|---|
| Bytes | 104,318 | 12,840 | −87.7% |
| Description chars | 1,012 | 214 | −78.8% |
| Sections | 18 | 9 | −50.0% |
| DUP matches | 7 | 0 | −100% |
| NOOP matches | 12 | 1 | −91.7% |

If you can't fill the table, you didn't measure. "I made it shorter"
without bytes is not a refactor report.
