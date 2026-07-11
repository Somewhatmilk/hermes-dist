#!/usr/bin/env python3
"""
T10 retention smoke test.

Seeds the in-memory DB with synthetic events aged 100 days (across all
event_types), then runs run_retention() and asserts the per-bucket split
matches the policy:
  - tool_invocation older than 30d -> archived
  - launch / error older than 90d -> archived
  - launch / error 30-90d old -> kept
  - tool_invocation 15d old -> kept
  - install / consent_change / quarantine_escalation 100d old -> kept (indefinite)
"""
import sys
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Force the scheduler off and use a temp DB
os.environ["RELAY_DISABLE_SCHEDULER"] = "1"

from app import sqlite_store


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix="relay-t10-test-"))
    db_path = tmpdir / "relay.db"
    print(f"using {db_path}")

    sqlite_store.init_db(db_path)

    # Register a user so events have a valid FK
    sqlite_store.register_user(
        uuid_str="test-user-uuid-aaaa-bbbb-cccc-dddddddddddd",
        hmac_secret="x" * 64,
        os="test",
        version="t10-smoke",
        opted_in=True,
        db_path=db_path,
    )

    # Build a timeline:
    now = datetime.now(timezone.utc)
    ages = {
        "tool_invocation_old":          (now - timedelta(days=100), "tool_invocation", 5),
        "tool_invocation_fresh":        (now - timedelta(days=15),  "tool_invocation", 3),
        "launch_old":                   (now - timedelta(days=100), "launch",          4),
        "launch_fresh":                 (now - timedelta(days=45),  "launch",          2),
        "error_old":                    (now - timedelta(days=100), "error",           6),
        "error_fresh":                  (now - timedelta(days=45),  "error",           1),
        "install_old":                  (now - timedelta(days=200), "install",         1),
        "consent_change_old":           (now - timedelta(days=200), "consent_change",  1),
        "quarantine_escalation_old":    (now - timedelta(days=200), "quarantine_escalation", 1),
        "unclassified_old":             (now - timedelta(days=100), "some_new_type",   2),
    }

    # Insert directly via the DB so we can backdate received_at (store_event
    # stamps now()).
    import sqlite3
    with sqlite_store.get_conn(db_path) as conn:
        for name, (ts, etype, count) in ages.items():
            iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(count):
                conn.execute(
                    "INSERT INTO events (uuid, event_type, received_at, payload, payload_size, signature_valid) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-user-uuid-aaaa-bbbb-cccc-dddddddddddd", etype, iso,
                     f"{name}:{i}".encode(), len(f"{name}:{i}"), 1),
                )

    # Snapshot live counts by type
    with sqlite_store.get_conn(db_path) as conn:
        live_by_type = dict(conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type").fetchall())
    print(f"seeded live_by_type: {live_by_type}")

    # Run retention
    summary = sqlite_store.run_retention(now=now, db_path=db_path)
    print(f"retention summary: {summary}")

    # Snapshot post-retention
    with sqlite_store.get_conn(db_path) as conn:
        live_after = dict(conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type").fetchall())
        archive_by_type = dict(conn.execute("SELECT event_type, COUNT(*) FROM events_archive GROUP BY event_type").fetchall())
        archive_total = conn.execute("SELECT COUNT(*) FROM events_archive").fetchone()[0]
        live_total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    print(f"live_after:    {live_after}")
    print(f"archive_by_type: {archive_by_type}")
    print(f"live_total={live_total} archive_total={archive_total}")

    # ─── Assertions ───
    ok = True
    def check(label, actual, expected):
        nonlocal ok
        if actual == expected:
            print(f"  ✓ {label}: {actual}")
        else:
            print(f"  ✗ {label}: expected {expected}, got {actual}")
            ok = False

    # tool_invocation: 5 old archived, 3 fresh kept
    check("tool_invocation archived", archive_by_type.get("tool_invocation", 0), 5)
    check("tool_invocation live", live_after.get("tool_invocation", 0), 3)
    # launch: 4 old archived, 2 fresh kept
    check("launch archived", archive_by_type.get("launch", 0), 4)
    check("launch live", live_after.get("launch", 0), 2)
    # error: 6 old archived, 1 fresh kept
    check("error archived", archive_by_type.get("error", 0), 6)
    check("error live", live_after.get("error", 0), 1)
    # install / consent_change / quarantine_escalation: indefinite
    check("install archived", archive_by_type.get("install", 0), 0)
    check("install live", live_after.get("install", 0), 1)
    check("consent_change archived", archive_by_type.get("consent_change", 0), 0)
    check("consent_change live", live_after.get("consent_change", 0), 1)
    check("quarantine_escalation archived", archive_by_type.get("quarantine_escalation", 0), 0)
    check("quarantine_escalation live", live_after.get("quarantine_escalation", 0), 1)
    # unclassified: 90d default, 100d old → archived
    check("unclassified archived", archive_by_type.get("some_new_type", 0), 2)
    check("unclassified live", live_after.get("some_new_type", 0), 0)

    # Stats endpoint
    stats = sqlite_store.get_storage_stats(db_path=db_path)
    print()
    print("storage stats (relevant fields):")
    print(f"  events.total = {stats['events']['total']}")
    print(f"  events_archive.total = {stats['events_archive']['total']}")
    print(f"  eligible_for_archive_now = {stats['eligible_for_archive_now']}")
    print(f"  retention_policy_days = {stats['retention_policy_days']}")
    print(f"  default_retention_days = {stats['default_retention_days']}")
    print(f"  next_archive_run_local = {stats['next_archive_run_local']}")
    print(f"  db_size_bytes = {stats['db_size_bytes']}")

    check("stats live total", stats["events"]["total"], live_total)
    check("stats archive total", stats["events_archive"]["total"], archive_total)
    check("stats eligible_now = 0 (we just archived)", stats["eligible_for_archive_now"], 0)
    check("stats install = indefinite (None)", stats["retention_policy_days"]["install"], None)
    check("stats tool_invocation = 30", stats["retention_policy_days"]["tool_invocation"], 30)
    check("stats default = 90", stats["default_retention_days"], 90)

    # Re-running should be a no-op (idempotent)
    print()
    print("re-running retention (should be no-op):")
    summary2 = sqlite_store.run_retention(now=now, db_path=db_path)
    print(f"  summary: {summary2}")
    check("re-run total_moved = 0", summary2["total_moved"], 0)

    print()
    if ok:
        print("=== ALL CHECKS PASSED ===")
        sys.exit(0)
    else:
        print("=== SOME CHECKS FAILED ===")
        sys.exit(1)


if __name__ == "__main__":
    main()