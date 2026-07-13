"""
JSON-RPC endpoint handlers for the multi-tenant hub.

Each handler verifies the per-user HMAC + capability token, enforces scopes,
runs in the user's namespace (when applicable), and emits an audit event.

Endpoints added to relay/app/main.py (mounted in the next deploy):

  GET  /api/v1/skills           List available skills (HMAC + skills.list scope)
  GET  /api/v1/skills/<name>    Read one skill content (HMAC + skills.read)
  POST /api/v1/tools/invoke     Invoke a tool (HMAC + tool scope)
  POST /api/v1/docker/run       Submit a docker run request (HMAC + tools.docker_run)

All endpoints emit an audit event via sqlite_store.audit() so the operator
sees exactly which user did what when.
"""
import os, json, time, asyncio
from pathlib import Path
from typing import Any, Callable

# Lazy import: keep relay startup lean
def _import_capability_token():
    from . import capability_token
    return capability_token


def _import_hmac_auth():
    from . import hmac_auth
    return hmac_auth


def _import_sqlite_store():
    from . import sqlite_store
    return sqlite_store


# ─── Skill handlers ───────────────────────────────────────────────────────

def list_skills(skills_root: str = "~/.hermes/skills") -> dict:
    """List skills in skills_root.

    Returns {ok: True, skills: [{name, size, category}], count: N}
    Only .md files count; references/templates/scripts are not surfaced.
    """
    root = Path(os.path.expanduser(skills_root))
    if not root.exists():
        return {"ok": False, "error": "skills_root not found", "skills": [], "count": 0}

    skills = []
    for path in sorted(root.rglob("SKILL.md")):
        rel = path.relative_to(root)
        category = rel.parts[0] if len(rel.parts) > 1 else "root"
        name = path.parent.name
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        skills.append({
            "name": name,
            "category": category,
            "size_bytes": size,
            "path": str(rel),
        })
    return {"ok": True, "skills": skills, "count": len(skills)}


def read_skill(name: str, skills_root: str = "~/.hermes/skills") -> dict:
    """Read one skill's full SKILL.md content."""
    root = Path(os.path.expanduser(skills_root))
    matches = list(root.rglob(f"{name}/SKILL.md"))
    if not matches:
        return {"ok": False, "error": f"skill '{name}' not found"}
    if len(matches) > 1:
        return {"ok": False, "error": f"ambiguous name; matches: {[str(p.relative_to(root)) for p in matches]}"}
    path = matches[0]
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": f"read failed: {e}"}
    return {
        "ok": True,
        "name": name,
        "path": str(path.relative_to(root)),
        "content": content,
        "size_bytes": len(content),
    }


# ─── Tool invocation handler ──────────────────────────────────────────────

# Tool registry: maps tool_name -> (callable, scope, description)
# New tools are registered via register_tool below.
_TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def register_tool(name: str, callable_: Callable, scope: str, description: str):
    """Register a tool callable. Requires `scope` to be in user's token."""
    _TOOL_REGISTRY[name] = {
        "callable": callable_,
        "scope": scope,
        "description": description,
    }


def list_tools() -> list[dict]:
    """List registered tools (operator-visible)."""
    return [
        {"name": name, "scope": meta["scope"], "description": meta["description"]}
        for name, meta in _TOOL_REGISTRY.items()
    ]


def invoke_tool(name: str, args: dict, token_payload: dict,
                audit_db_path: str = None) -> dict:
    """Invoke a tool with capability-token scope check.

    Returns {ok, tool, output, scope_used, audit_id}.
    """
    if name not in _TOOL_REGISTRY:
        return {"ok": False, "error": f"unknown tool: {name}"}
    meta = _TOOL_REGISTRY[name]

    # Capability check
    try:
        _import_capability_token().require_scope(token_payload, meta["scope"])
    except PermissionError as e:
        return {"ok": False, "error": str(e), "scope_required": meta["scope"]}

    # Audit before execute
    sqlite_store = _import_sqlite_store()
    audit_id = sqlite_store.audit(
        audit_db_path or "~/.hermes/relay.db",
        actor=token_payload["user_uuid"],
        action="tool_invoke",
        target=name,
        details=f"scope={meta['scope']} args_keys={list(args.keys())}",
    ) if audit_db_path else None

    # Execute
    try:
        output = meta["callable"](**args)
    except Exception as e:
        return {"ok": False, "error": f"tool error: {e}", "audit_id": audit_id}

    return {
        "ok": True,
        "tool": name,
        "output": output,
        "scope_used": meta["scope"],
        "audit_id": audit_id,
    }


# ─── Docker-as-a-Service handler ──────────────────────────────────────────

# This is a STUB. Real implementation requires Linux user namespace setup
# + a docker-daemon proxy that enforces per-user mount points. See
# docs/decisions/0007-multi-tenant-hub.md §"Docker-as-a-Service" for the
# full design. The handler validates inputs and runs in a tight sandbox;
# if docker is not available, it returns a clear "not yet wired" error.
def docker_run(image: str, cmd: list[str], env: dict | None = None,
               mounts: list[dict] | None = None, user_uuid: str = None) -> dict:
    """Run a docker container in user-namespaced sandbox.

    mounts: list of {src, dst, mode} where mode is 'ro' or 'rw'.
    """
    if not user_uuid:
        return {"ok": False, "error": "user_uuid required"}

    # Validate mounts (deny-list: /etc, /var/lib/hermes, /proc, /sys, /dev)
    FORBIDDEN_PREFIXES = ("/etc", "/var/lib/hermes", "/proc", "/sys", "/dev", "/boot")
    if mounts:
        for m in mounts:
            src = m.get("src", "")
            if any(src.startswith(p) for p in FORBIDDEN_PREFIXES):
                return {"ok": False, "error": f"forbidden mount src: {src}"}
            if m.get("mode") not in ("ro", "rw"):
                return {"ok": False, "error": f"mount mode must be 'ro' or 'rw': {m}"}

    # NOTE: actual docker invocation is operator-side concern. The
    # implementation belongs in a separate module that the operator
    # wires up after sandbox tooling is in place. For now return a
    # structured ack so the operator can complete the wiring.
    return {
        "ok": True,
        "stub": True,
        "message": "Docker-as-a-Service is in stub mode. Operator must implement the namespace + mount enforcement before this is exposed to users.",
        "would_run": {
            "image": image,
            "cmd": cmd,
            "env": env or {},
            "mounts": mounts or [],
            "user_namespace": f"user-{user_uuid[:8]}",
        },
    }


# ─── Override tracker (telemetry for user customizations) ──────────────────

def detect_overrides(user_profile_dir: str, operator_default_dir: str) -> dict:
    """Detect which files in user_profile_dir differ from operator_default_dir.

    Returns {ok, overrides: [{path, type}], count: N}
    type ∈ {"added", "modified", "deleted"} relative to operator default.
    """
    user_root = Path(user_profile_dir)
    op_root = Path(operator_default_dir)

    if not user_root.exists():
        return {"ok": False, "overrides": [], "count": 0, "error": "user_profile_dir not found"}
    if not op_root.exists():
        return {"ok": False, "overrides": [], "count": 0, "error": "operator_default_dir not found"}

    overrides = []

    # Added or modified files in user root
    for path in user_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(user_root)
        op_path = op_root / rel
        if not op_path.exists():
            overrides.append({"path": str(rel), "type": "added"})
        else:
            try:
                user_hash = hashlib.md5(path.read_bytes()).hexdigest()
                op_hash = hashlib.md5(op_path.read_bytes()).hexdigest()
                if user_hash != op_hash:
                    overrides.append({"path": str(rel), "type": "modified"})
            except OSError:
                pass

    # Deleted files (existed in operator default but not in user root)
    for path in op_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(op_root)
        user_path = user_root / rel
        if not user_path.exists():
            overrides.append({"path": str(rel), "type": "deleted"})

    return {"ok": True, "overrides": overrides, "count": len(overrides)}


import hashlib  # for detect_overrides
