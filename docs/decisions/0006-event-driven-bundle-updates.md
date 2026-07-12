# RFC 0006: Replace the 60s heartbeat with event-driven bundle updates

**Status:** Draft — awaiting operator sign-off
**Author:** kanban worker t_bb03ba31 (default profile), 2026-07-12
**Affects:** T3 (`POST /api/v1/profile-bundle` + 60s client heartbeat), `relay/client/heartbeat.sh`, all three OS installers
**Goal of this RFC:** decide whether to replace the 60s heartbeat polling loop in T3 with an event-driven bundle-update mechanism, and pick the path.

---

## 1. Context

T3 (done, `t_2cd44edf`) wired up the push-update channel:

- `POST /api/v1/profile-bundle` — operator publishes a bundle (HMAC-authenticated operator token).
- `GET /api/v1/profile-bundle?since=<unix_ts>` — user fetches the latest bundle newer than `since` (HMAC-authenticated user identity).
- `relay/client/heartbeat.sh` runs every 60s as a Task Scheduler job (Windows), a systemd user service (Linux), or a launchd plist (macOS). Each tick: GET, advance `since`, apply if newer.
- The relay always returns `server_time_unix` so the client can advance its `since` pointer even when `up_to_date=true`.

The 60s cadence is the **floor** of update latency: a published bundle can sit in the relay for up to 59s before a connected client sees it. For a dormant user (laptop closed), the heartbeat is paused entirely — the update waits until they next log in. That's actually fine because the safety net is "user opens laptop → heartbeat resumes → fetches bundle". So the *correctness* is fine; the only cost is **redundant traffic** for active users who don't change anything.

This RFC asks: can we keep the correctness and remove the redundant traffic?

## 2. Three options on the table

### Option A — Server push (WebSocket / long-poll)

Relay holds an open socket per user; pushes a small "new bundle available" frame when `POST /api/v1/profile-bundle` lands. Client applies on receipt.

| Criterion | Score | Notes |
|---|---|---|
| Worst-case latency | ~1s | Network round-trip from POST to client. |
| Server infra cost | **High** | One persistent TLS+WS socket per connected user; needs ping/pong keepalive; needs backpressure when a client is offline. |
| Corporate-proxy friendliness | **Bad** | Many corp proxies silently strip idle WS connections. Tailscale punches through, but if a user ever runs hermes outside Tailscale the WS will drop, leaving the push model invisible until they next poll (which we still need anyway). |
| Idle overhead | Low for active users, high for dormant ones | Active user = one socket that pays for itself. Dormant user = socket held open doing nothing for days. |
| Sleeping-client handling | Needs backfill | Sleep → push missed → on wake, server either replays from a queue (basically polling) or relies on the client to GET. So either we run a *push + pull-on-wake* hybrid, or push is unreliable. |

**Verdict: not recommended.** Push on top of Tailscale gives us ~0s of latency improvement over a 60s poll, but forces us to maintain a WS server, a per-user connection table, and a fallback path anyway. The cost/benefit only flips if we have hundreds of concurrent connected users; with the current hermes-dist rollout (~5 devices on this tailnet per SHIP.md), it's not worth it.

### Option B — GitHub Actions webhook on operator `git push`

GitHub Actions workflow fires on `push` to `master` of `Somewhatmilk/hermes-dist`. The workflow POSTs the new bundle to `POST /api/v1/profile-bundle` automatically. The client polling loop is **unchanged**.

| Criterion | Score | Notes |
|---|---|---|
| Worst-case latency | **Unchanged from T3** (~60s, plus GitHub's ~5-15s webhook delivery) | Because the client still polls on the same 60s timer. The webhook only saves the operator the manual POST step. |
| Server infra cost | Low | One new endpoint, ~30 lines: `POST /api/v1/webhook/github` that verifies `X-Hub-Signature-256` against a configured shared secret, parses the workflow payload, and either calls the existing `publish_profile_bundle` logic or just `200`s after a side-effect. |
| Corporate-proxy friendliness | **Same as T3 today** | No change on the client side. |
| Idle overhead | **Same as T3 today** | No change on the client side. |
| Sleeping-client handling | **Same as T3 today** | No change on the client side. |
| Operator ergonomics | **High** | Operator no longer has to remember to POST a bundle; pushing a tagged release to GitHub is the publish event. Eliminates a class of "I shipped the code but forgot to push the bundle" bugs. |

**Verdict: optional enhancement, not a replacement.** On its own, B does not change client behavior at all — but it eliminates a manual operator step and gives us an audit trail via the workflow run. Pair B with C (below) and the full chain is: `git push` → GitHub Actions → webhook → relay publishes → next client trigger → user has new bundle.

### Option C — Event-driven client triggers (recommended)

Replace the wall-clock 60s timer with three triggers, plus a single daily safety-net poll:

1. **Hermes startup** — the install script (already runs on login via Task Scheduler / systemd-user / launchd) calls `hermes-dist-heartbeat --once` after launching the daemon. New bundle is in place before the user's first turn.
2. **Post-turn hook** — at the end of every hermes turn, the agent shell calls `hermes-dist-heartbeat --once &` (backgrounded, non-blocking, fast-fail). Latency from publish → user-actually-runs-with-new-bundle = at most one turn length (30-300s in active use).
3. **Operator-initiated** — explicit `hermes update` command runs `--once` immediately.
4. **Daily safety-net poll** — Task Scheduler / systemd timer / launchd `StartCalendarInterval` runs `--once` once a day to catch anything the first three missed (e.g. user running a non-hermes session all day). Replaces the 60s timer; same wall-clock mechanism, 1440× less frequent.

The `poll_once` function in `heartbeat.sh` already supports `HEARTBEAT_ONCE=1`, so this is **pure orchestration, not new logic**.

| Criterion | Score | Notes |
|---|---|---|
| Worst-case latency (active user) | ~one turn (30-300s) | Same order of magnitude as today's 60s, often faster (post-turn fires immediately). |
| Worst-case latency (dormant user) | **Up to 24h** before next daily poll, OR instant on next hermes startup | The hermes-startup trigger catches "laptop was closed, user opens it and runs a turn" — which is the case that matters most for a dormant user. The 24h daily timer is a pure belt-and-suspenders for users who haven't opened hermes in days and the operator wants to reach. |
| Server infra cost | **Zero** | Same endpoints, same GET, same apply. Only the client orchestration changes. |
| Corporate-proxy friendliness | **Same as T3 today** | No change. |
| Idle overhead | **Near zero** | One GET on hermes startup, one GET per turn end, one GET per day. For an active 8h workday doing ~30 turns/hour that's ~240 GETs/day, down from 1440. For a dormant user, 1 GET/day. |
| Sleeping-client handling | **Improved** | The hermes-startup trigger fires whenever the user opens a session; the post-turn hook fires whenever they're active. There's no "wake-up window" gap. |

**Verdict: recommended.** Solves the actual problem (wasted traffic) without changing the relay, without adding a new server, without losing any of T3's correctness guarantees.

## 3. Recommendation

**Option C as default. Option B as optional enhancement. Option A rejected.**

**Why C over A:** A's only advantage is ~1s latency improvement over a 60s poll, which disappears as soon as any client runs outside Tailscale (corp proxy) or sleeps. C gets us ~one-turn latency with zero new server surface and full Tailscale-or-not parity.

**Why B on top of C:** B is orthogonal to C — it removes an operator-step (manual POST), not a client-step (poll). Together: `git push` → GitHub webhook → relay publishes → next client trigger (startup / post-turn / daily) → bundle applied. The end-to-end latency from operator intent to applied update is "as fast as the user types their next turn", which is what users actually feel.

**Why not A even with B:** the two don't compose — push needs a separate socket that doesn't help the dormant user, and the dormant user is where polling already costs the least (zero polls while asleep). A is solving the wrong problem.

## 4. Worst-case latency under the recommendation

- Active user (turns every 30s-300s): new bundle applied within one turn length of the next turn boundary. Worst-case: 5min if a user walks away mid-turn.
- Active user who just turned off their laptop after `git push`: bundle applied within ~10s of next laptop-open (hermes startup trigger).
- Dormant user (no hermes sessions for days): bundle applied within 24h (daily safety-net) or instantly on next session-start (whichever first).
- Operator did the push but their own PC is asleep: the bundle is on the relay the moment the webhook fires. Their own client picks it up on wake. This is the same as T3 today.

**What triggers an update under C:** (a) hermes daemon start, (b) end of an agent turn, (c) explicit `hermes update`, (d) the daily scheduled poll.

## 5. Implementation sketch (for the next task — NOT this RFC's deliverable)

When the user signs off on C (+ optional B), spawn:

- **T14 — Implement event-driven heartbeat client (Option C).**
  - Refactor `relay/client/heartbeat.sh`: keep `poll_once`, drop the infinite loop, add a `hermes-dist-heartbeat-once` shim.
  - Update `install-windows.ps1` heartbeat Task Scheduler job to run `StartWhenAvailable=true` daily (not every 60s).
  - Update `install-linux.sh`: switch from a looping systemd user service to a systemd timer firing daily.
  - Update `install-macos.sh`: switch from `StartInterval=60` to `StartCalendarInterval` once-a-day.
  - Add a post-turn hook wrapper: `~/.hermes/hooks/post-turn-hermes-dist.sh` that runs the `--once` shim in background.
  - Acceptance: a dry-run that POSTs a bundle and asserts the next hermes-startup + first-turn-end both apply it.

- **T15 — Add GitHub Actions webhook receiver (Option B, optional).**
  - New endpoint `POST /api/v1/webhook/github` (HMAC over `X-Hub-Signature-256` with shared secret).
  - Workflow file at `.github/workflows/publish-hermes-dist.yml` that POSTs the bundle on tagged release.
  - Acceptance: `git tag v0.X.Y && git push --tags` → bundle appears in relay without manual operator POST.

## 6. Out of scope (this RFC)

- Modifying T3's existing endpoints or the on-the-wire bundle format.
- Modifying `heartbeat.sh`'s `poll_once` or `apply_bundle` logic.
- Adding the GitHub Actions workflow (that's T15).
- WebSocket / long-poll server push (Option A) — rejected.
- Any change to the relay's auth model (HMAC, operator token, denylist).

## 7. Sign-off

Operator: please respond with one of:

1. **Approve C (+ optional B)** — spawn T14 first, T15 if you want the webhook.
2. **Reject C, prefer A** — explain which proxy/sleeping-client scenario is the actual blocker that C doesn't solve; I haven't found one but I might be missing your context.
3. **Reject both, keep T3 polling** — current 60s loop stays.
4. **Other** — different framing, different criteria, different priority.

Reply recorded as a comment on kanban task `t_bb03ba31`. RFC moves out of Triage once sign-off is captured.

## 8. Appendix — file references

- `relay/client/heartbeat.sh` — the current polling client (lines 213-222 are the infinite loop).
- `relay/app/main.py` lines 531-585 — the GET endpoint contract this RFC inherits unchanged.
- T3 task body (`t_2cd44edf` on kanban board `tailscale`) — what we're proposing to replace.
- SHIP.md v0.4.0 design note — references the earlier direction of "user-initiated `hermes update-dist`". C coexists with that: explicit `hermes update` is one of C's four triggers.