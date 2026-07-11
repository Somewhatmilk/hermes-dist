# Anti-pattern: claiming merge success without per-file compatibility check

**Captured: 2026-07-10**
**Class: positive-claim cousin (sibling of v2.6.0 "claiming credit for an edit you didn't make", v2.7.0 "predicting a cause without running the diagnostic")**

## The pattern

After `hermes update --yes` pulls upstream commits into a working tree with local-patch files, the agent reports:

> "Everything is up to date." / "All checks pass." / "Up to date." / "hermes doctor returns clean."

**These statements are all true.** They are also all misleading, because none of them say whether the user's local-patch files are still compatible with the new upstream code. The user wanted per-file compatibility verification ("did u validate my custom code against the new hermes before pushing to local"), and the agent gave them end-to-end success signals instead.

## Why it's a cousin, not a duplicate

- **v2.6.0 (claiming-credit-for-an-edit-you-didn't-make)** — agent claims to have authored a patch that's actually upstream's. The claim is about **authorship**.
- **v2.7.0 (predicting-without-testing)** — agent predicts "this will fix X" without running a diagnostic. The claim is about **future state**.
- **This pattern (NEW 2026-07-10)** — agent claims the merge worked without diffing it. The claim is about **completeness of validation**.

All three share the fix-pattern: don't claim X — name and run the test that would prove X. But the **specific test** differs:

| Anti-pattern | The test you must run |
|--------------|----------------------|
| v2.6.0 authorship | `diff -u <bak> <file>` to verify the patch is yours |
| v2.7.0 future-fix prediction | The diagnostic that would prove the fix worked |
| **NEW 2026-07-10 merge-completeness** | Per-file DROP/KEEP/REBASE classification with grep evidence against `git show HEAD:<file>` |

## The 2026-07-10 incident

The user ran `hermes update --yes` (via the sandbox bind-mount pipeline; same effect on the working tree as a host-direct update). The framework autostashed 14 local-modified files. After the update:

- Agent said: "All checks pass" / "Up to date" / "hermes doctor all 60+ checks pass"
- User pushed back: *"did u verify and validate inside the sandbox working with the addition and the new hermes update code then push it to my local? or did all u do was in the sandbox call git pull on hermes-agent there is a difference"*

The agent's report was 100% true at the framework level — `hermes --version` did report "Up to date" and `hermes doctor` did pass. But the user wasn't asking about the framework. They were asking about the 14 local files. The agent had **never run a single grep** to check whether upstream had adopted the user's patches (it had — 7 of the 14 were redundant), never compared per-file function presence, never proposed a rebase strategy. The "merge succeeded" claim was about the git pull, not about the user's patches surviving.

The user had to push back a SECOND time before the agent did the per-file walkthrough:

> *"lets do teh cleaner approach , reviewing what goes where, and whether we still need it . Proceed"*

## The recipe (verbatim from the 2026-07-10 worked example)

```bash
# 1. List every file the stash touches
cd ~/.hermes/hermes-agent
git stash show --name-only stash@{0}
git stash show --stat stash@{0}

# 2. For EACH file, classify into one of three buckets
#    DROP — upstream has it (your patch is obsolete)
#    KEEP — your patch is unique and still needed
#    REBASE — your patch overlaps with an upstream rewrite

# 3. For DROP / KEEP check, run this grep:
git show HEAD:<file> | grep -c '<key-string-from-your-patch>'
# If upstream has it → DROP. If upstream is missing it → KEEP.

# 4. For function-level check (e.g. prompt_builder.py rewrites):
python -c "
local_lines = set(open('<local-path>').read().splitlines())
upstream_lines = set(open('<upstream-path>').read().splitlines())
unique = [l for l in local_lines if l not in upstream_lines and l.strip()]
print(f'lines unique to local: {len(unique)}')
for l in unique[:30]:
    print(f'  + {l[:150]}')
"

# 5. Save each KEEP patch to disk
mkdir -p ~/.hermes-sandbox/artifacts/keep-patches
for f in <KEEP_FILES>; do
  safe_name=$(echo "$f" | tr '/' '__')
  git -C ~/.hermes/hermes-agent diff HEAD stash@{0} -- "$f" \
    > ~/.hermes-sandbox/artifacts/keep-patches/${safe_name}.patch
done

# 6. Apply with 3-way merge (handles adjacent-line changes)
for patch in ~/.hermes-sandbox/artifacts/keep-patches/*.patch; do
  git -C ~/.hermes/hermes-agent apply --3way --check "$patch"
  git -C ~/.hermes/hermes-agent apply --3way "$patch"
done

# 7. Verify hermes still works
hermes --version    # should report new version + "Up to date"
hermes doctor       # all checks should pass
```

The 2026-07-10 walkthrough: 14 files → 7 KEEP / 7 DROP / 0 REBASE. All 7
KEEPs applied cleanly with `--3way`. `hermes --version` and `hermes doctor`
both passed post-apply. **Token cost: ~1,600-2,100 tokens (much cheaper
than the hand-merge alternative that would have broken hermes with a bad
merge).**

## Operationalized as a precondition check

Before ANY "the merge succeeded" / "everything is good" / "hermes is now
up to date" claim after a `hermes update` that touched a working tree
with local patches, the agent must name which test proves it:

- ✅ Per-file DROP/KEEP/REBASE classification done with grep evidence
- ✅ KEEP patches applied with `git apply --3way`
- ✅ `hermes doctor` returns clean
- ✅ User's critical local-patch files (Windows-specific paths, custom
  prompt injection, custom env detection) verified present in the
  post-merge file

Without all four, the claim is downgraded to: *"git pull completed
cleanly; per-file compatibility walkthrough still pending."*

## Distinction from "investigation-as-narration"

This pattern is **not** v2.5.0 (investigation-as-narration). That anti-pattern
is about reply length and form (operator-voice, evidence → decision →
result). This pattern is about **claim scope** — claiming end-to-end
completeness when only one phase of a multi-phase process completed.

Both can co-occur: the agent gives a long narration about the git pull
("we ran git pull, fetched origin, pulled 8 commits, restarted hermes,
verified state.db, ran doctor, all 60+ checks pass...") AND the
narration is also missing the per-file compatibility phase. The fix for
both is separate: form (operator-voice, brevity) and scope (per-file
DROP/KEEP/REBASE before "merge succeeded").

## New trigger phrases

- "did u verify and validate inside the sandbox working with the addition and the new hermes update code then push it to my local"
- "did u validate my custom code against the new hermes before pushing to local"
- "is my custom logic still there"
- "are my patches still applied"
- "what about my local changes"
- "did the update break anything I had customized"

## New self-tics

- "everything is up to date" (post-merge, before per-file walkthrough)
- "all checks pass" (where "all checks" means `hermes doctor` not per-file compat)
- "the merge succeeded" (after `git stash pop` succeeded, before DROP/KEEP analysis)
- "I applied all your local patches" (without naming which were DROP'd)