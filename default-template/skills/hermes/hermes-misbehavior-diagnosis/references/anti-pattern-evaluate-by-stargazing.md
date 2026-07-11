# Anti-pattern: evaluate-by-stargazing (a.k.a. "did you even view it")

## What it looks like

The user pastes N URLs in one message — typically Reddit threads, GitHub repos,
Hacker News threads, or tool-recommendation roundups — and asks for evaluation
or "should we use this". The agent:

1. Fetches the URLs (good).
2. Reads the **thread body / README first paragraph** (insufficient).
3. Skims the inline links in comments (insufficient).
4. Concludes based on **surface signals** — star count, last commit date,
   contributor count, "looks rough", "1 author", "small project" — without
   actually loading the linked repos and reading their code/docs.

## Why it's a Class-1 failure

This is **extrapolation on top of incomplete observation**. The thread body is
a pointer; the value lives in the things the commenters link to. Star count
can mislead (high stars + abandoned = bad; low stars + active recent commits
+ clear architecture + solves a real problem = good). "Looks rough" reflects
the README's polish, not the codebase's quality.

User pushback phrasing that signals this anti-pattern has fired:

- "did you even view it"
- "did you even check if"
- "why aren't you reviewing [the linked things]"
- "you just dismissed it without trying"
- "do the actual research, not the title"

## The correct procedure

When the user gives ≥3 URLs about tools/libraries/alternatives in one message:

1. **Read every URL the user provided.** (You were doing this — don't stop.)
2. **For each URL**, enumerate every named repo/tool/library/CLI/project
   mentioned in the text or comments. This is the explicit extraction step
   that's easy to skip.
3. **For each extracted repo**, fetch its page (GitHub project page, npm/PyPI
   page, official docs) and read at minimum:
   - Stars, last commit date, contributor count
   - Recent commit messages (reveals what the project actually does now)
   - LICENSE
   - Architecture (one-paragraph summary from the README or skill/manifest)
   - Whether it's actively maintained vs. abandoned
4. **Compare against current stack** — does it overlap? replace? extend?
5. **Report findings ranked** by relevance to user's stated need, not by
   star count.

For a single URL, the same rule applies: **always fetch and read the linked
project, not just the page that links to it.** A user's "check this tool"
implicitly asks about the tool, not the article.

## Example from 2026-07-03 (today)

User gave 5 URLs from Reddit including:
- r/LocalLLaMA on "best local model for fast summarization"
- r/LocalLLaMA on "free local web-search for LLM agents"
- r/LocalLLaMA showcasing `MarcellM01/TinySearch` (linked in OP body)
- r/hermesagent on "best web scraping tool for Hermes" mentioning
  `Johell1NS/browser-search` (linked by commenters)
- GitHub repo for `browser-use/browser-harness` (directly named)

Agent read all 5 URLs but did NOT fetch any of the linked repos. Replied
"skip these, your existing stack covers it" without installing/reading.
User pushback was immediate: *"why aren't you reviewing them"*.

After correction, agent fetched `MarcellM01/TinySearch` — found it was
actively maintained (48 commits, last commit 5 days ago), used Crawl4AI
as a backend, defaulted to SearXNG (user's existing stack), bundled as a
single `docker compose` deploy, exposed MCP tools. **Installed it.** This
filled a real gap the agent had dismissed at surface level.

The error was not laziness — it was a missing step in the procedural model
("always read what comments link to"). This is a procedural-add, not a
data fix.

## How to bake it in

Add as an explicit step in any future "evaluate these URLs" task. The trap
is reading the wrapper (the user's pasted URL) without reading the wrapped
content (the repos/comments inside the URL body). Treat every fetched page
as a graph, not a leaf — outgoing links have content.

See `hermes-self-improvement/references/lessons-L1-L18.md` for the
adjacent principle: **research-first** means go deeper than the surface,
not just confirm what's already skimmed.
