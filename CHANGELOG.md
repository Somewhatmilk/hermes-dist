# Changelog

All notable changes to hermes-dist are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — comprehensive distribution pass (branch: feature/comprehensive-distribution-pass)

**Phase 1: Cross-OS installers**
- `install-common/common.sh` — shared installer logic (distro detect, prereq checks, repo clone, daily-pull scheduler)
- `install-common/heartbeat.sh` — push-update channel client; polls relay every ~30s
- `install-unix.sh` — full rewrite: distro-aware (Debian/Ubuntu, Fedora/RHEL, Arch, Alpine) via `/etc/os-release`; systemd user timer or cron fallback
- `install-macos.sh` — NEW: Homebrew + launchd plist registration; Apple Silicon + Intel aware
- `install-windows.ps1` — Python 3.11+ detection (python3/python/py); Git Bash discovery; Windows Task Scheduler heartbeat
- `winget/Somewhatmilk.hermes-dist.{yaml,installer.yaml,yaml.version}` — winget package manifest

**Phase 2: Push-update channel**
- `relay/app/manifest_store.py` — `manifest_versions` + `user_installed_versions` tables; `publish_manifest()`, `get_latest_manifest()`, `record_user_heartbeat()`
- `relay/app/main.py` — `GET /api/v1/manifest`, `POST /api/v1/heartbeat-ack`, `POST /api/v1/release`, `GET /api/v1/installed`
- `relay/hermes-dist-operator.py` — operator CLI: `publish`, `show`, `installed`, `rollback`, `pin-user`

**Phase 3: Scraper pool (per (user_uuid, persona_id))**
- `relay/app/scraper_jobs.py` — `scrape_jobs` + `scrape_results` schemas; `data_origin='relay_passive_scrape'`
- `relay/app/scraper_router.py` — slot pool keyed on (user, persona); LRU eviction with privacy-respecting cookie wipe; per-slot Camofox session dir
- `relay/app/main.py` — `POST /api/v1/scrape`, `GET /api/v1/scrape/result/{job_id}`, `POST /api/v1/scrape/slot/cookies`, `GET /api/v1/scrape/jobs` (operator)

**Phase 4: Peer memory isolation (preview-only)**
- `relay/app/peer_index.py` — preview-only schema; `MAX_PREVIEW_CHARS = 280` enforced at server; no `full_content` column anywhere
- `default-template/scripts/peer_index_local.py` — user-side mirror for the import flow
- `default-template/scripts/mnemosyne_dist.py` — `internal_thought()` and `external_data()` as the ONLY two memory writers; `wrap_external()` stamps origin metadata at every prompt build; CHECK constraint mirrors `source IN ('internal','external')`

**Phase 5: Privacy + governance**
- `docs/PRIVACY.md` — three-circle boundary (PUBLIC repo / user hermes / operator-only); five enforcement layers; what's allowed vs forbidden in commits
- `.gitignore` — operator-private paths explicitly blocked: `.hermes/`, mnemosyne DBs, `.env`, research notes, scrape cache, etc.

**Phase 6: Audit UI**
- `relay/app/dashboard.py` — FastAPI router with cookie-session login (HMAC-signed); 11 dashboard pages
- `relay/app/templates/*.html` — overview, installed, events, audit, scrape pool, peer index, release form

**Tests**
- `tests/test_peer_index.py` — 9 tests covering preview truncation, source/reliability/origin_kind validation, ownership, recall counter
- `tests/test_mnemosyne_dist.py` — 9 tests covering the two-writer discipline, schema CHECK, wrap_external at prompt build, schema-violation refusal
- All 18 tests pass.

## [0.1.0] - 2026-07-06

### Added
- Initial PoC: FastAPI relay with HMAC-signed event submission, registration, audit log
- `default-template/` user-facing profile bundle
- `install-windows.ps1` (single-OS PoC)
- `install-unix.sh` (933-byte stub)
- `default-template/SOUL.md`, `default-template/config.yaml` with restricted toolsets

[Unreleased]: https://github.com/Somewhatmilk/hermes-dist/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Somewhatmilk/hermes-dist/releases/tag/v0.1.0