# Privacy Boundary — hermes-dist

This document specifies what the relay can see, what users can see, and what
only the operator can see. It is the contract that backs every architectural
choice in the project.

## TL;DR — three concentric circles

```
┌──────────────────────────────────────────────────────────────┐
│  OUTER: PUBLIC repo                                          │
│  ──────────────────                                          │
│  The hermes-dist GitHub repo. Anyone can read it.            │
│  Contains: installers, default-template, relay code, docs.   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  MIDDLE: user hermes installs                           │     │
│  │  ────────────────────────────────                      │     │
│  │  Each small-group user has their own hermes install.   │     │
│  │  Contains: their own Mnemosyne DB (memories), their    │     │
│  │  own .env (their API keys), their own toolsets.        │     │
│  │  Per-user profile = their UUID, isolated.              │     │
│  │                                                          │     │
│  │  ┌──────────────────────────────────────────────────┐  │     │
│  │  │  INNER: operator-only                              │  │     │
│  │  │  ─────────────────                                │  │     │
│  │  │  The operator's laptop. Never shared.              │  │     │
│  │  │  Contains: hermes-dist-operator.env, operator's    │  │     │
│  │  │  own Mnemosyne, research notes, dev branches.      │  │     │
│  │  └──────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

## What the PUBLIC repo can contain (and what it MUST NOT)

| Allowed | Forbidden |
|---|---|
| `install-*.{ps1,sh}` | Operator's API keys |
| `default-template/SOUL.md` | Operator's Mnemosyne DB |
| `default-template/config.yaml` (template, no secrets) | Operator's own `.env` |
| `relay/` collector code | Operator's research notes |
| `docs/` architecture & runbooks | Operator's personal `~/.hermes/` contents |
| `install-common/` shared installer code | Operator-specific key files |
| `winget/` package manifest | Scrape results from operator's own use |

The `.gitignore` enforces this boundary mechanically. If you find
yourself wanting to `git add -f` something private, **stop**. There is
no good reason. Add it to your private repo / Notes app / password
manager instead.

## What the RELAY can see (the operator's collector)

The relay is hosted on the operator's PC (or NAS, or VPS). It can see:

| Sees | Doesn't see |
|---|---|
| Per-user install events (HMAC-signed) | What the user is doing *inside* hermes' reasoning |
| Skill submissions (if user opted in) | The user's API keys (HMAC auth uses per-user secret, not LLM keys) |
| Profile config diffs (if user opted in) | The user's Mnemosyne contents (only shared previews go to peer index) |
| Scrape jobs: which URL, which persona | What's on the user's disk |
| Scrape results: HTML bodies, status codes | The user's browsing history outside of submitted jobs |
| Audit log of every relay action | The user's local files |
| Peer index: 280-char previews of shared memories | Full content of peer's memories (architecturally impossible — never stored) |

## What USERS can see (each other, indirectly)

A user can:
- See the public repo contents (workflow, structure)
- See shared peer previews in the relay's peer index (when they call `/api/v1/peer/recall`)
- NOT see other users' full memories
- NOT see other users' install events (those are operator-only)
- NOT see other users' scrape results

## What ONLY THE OPERATOR can see

- Audit log of every action by every user
- Full install history (which version each user is on, last heartbeat)
- Released manifest versions and content
- Operator CLI (`hermes-dist-operator`) commands and their results
- The user's HMAC secret (issued by the relay at registration)

## The "no mirror" rule

The relay stores a **preview-only** peer index. There is no `full_content`
column anywhere. Architecturally, the relay cannot hold friend's full memory
content. If you find yourself wanting to add such a column, **stop**. It
violates the privacy model.

The same rule applies to scrape results: the relay holds raw HTML (because
the user wants the page content), but it does NOT share scrape results
across users. Each user's scrape results live in their own slots and are
only retrievable by them.

## How the boundary is enforced

Five layers, each with a different threat model:

1. **Filesystem (operator-only directories)** — `.gitignore` blocks accidental
   commits of operator-private content.
2. **Schema (SQLite CHECK constraints)** — `memory_items.source` must be
   `'internal'` or `'external'`; no other value can land in the DB.
3. **Single-purpose writers (Python)** — `internal_thought()` and
   `external_data()` are the only functions that write to `memory_items`.
   No code review should accept new direct inserts.
4. **HMAC-signed channels** — every user→relay request is signed with a
   per-user secret; the relay verifies before routing. The user cannot
   impersonate other users.
5. **Operator auth (separate token)** — operator endpoints require a
   different static token. A leaked user HMAC secret doesn't give the
   attacker operator powers.

## What the user is told

The first-launch onboarding script prompts:

> "This hermes-dist install can optionally forward certain events to the
> operator's collector. Events forwarded are:
>   - Skills you create (clean ones queued for review; flagged ones sent immediately)
>   - Memories you mark with submit_to_collector: true
>   - Scripts that match the security denylist (sent immediately, blocked from running)
> If you opt out, NO data leaves this machine. You can change this later."

This text is in `.onboard.sh` line 50ish. It is the consent receipt.

## When the boundary breaks

It breaks when the operator:
- Adds a column to peer_index that holds full content. **Don't.**
- Adds a `direct_paste_internal()` writer that bypasses `internal_thought()`.
  **Don't.**
- Commits their own Mnemosyne DB to the repo. **Don't.**
- Logs full request bodies to a place users can see. **Don't.**
- Treats `submit_to_collector: true` as the default for all memory.
  **Don't.**

The boundary is upheld by discipline more than by code. The code is the
supporting structure.