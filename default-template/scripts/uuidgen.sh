#!/usr/bin/env bash
# Portable UUIDv4 generator. Prefers uuidgen, falls back to /proc/sys/kernel/random/uuid.
# Used by .onboard.sh and the post-* hooks.

if command -v uuidgen >/dev/null 2>&1; then
  uuidgen | tr '[:upper:]' '[:lower:]'
elif [ -f /proc/sys/kernel/random/uuid ]; then
  cat /proc/sys/kernel/random/uuid
elif command -v python3 >/dev/null 2>&1; then
  python3 -c "import uuid; print(str(uuid.uuid4()))"
else
  echo "ERROR: no UUID generator found (need uuidgen, /proc/sys/kernel/random/uuid, or python3)" >&2
  exit 1
fi
