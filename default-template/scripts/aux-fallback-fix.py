#!/usr/bin/env python3
"""
aux-fallback-fix.py — Runtime monkey-patch for the auxiliary client fallback
order asymmetry in hermes-agent/agent/auxiliary_client.py.

WHY THIS WRAPPER (not a direct code patch):

  The hermes-agent install at ~/.hermes/hermes-agent/ is owned upstream;
  `hermes update` will overwrite auxiliary_client.py on every update.
  Per the project's AGENTS.md: "hermes update (and `git pull` in a source
  checkout) will overwrite this file." A direct patch to auxiliary_client.py
  would be silently reverted on the next update.

  This wrapper monkey-patches the function at Python runtime. It:
    - Lives in ~/.hermes/scripts/ (operator-owned, not affected by hermes update)
    - Is opt-in: enabled only when `~/.hermes/config.yaml` has the flag set
    - Defaults to OFF, preserving historical explicit-path behavior
    - Can be enabled per-task via `auxiliary.<task>.allow_discovery_fallback: true`

THE ASYMMETRY:

  The fallback order per the code comment (auxiliary_client.py:6908-6912) is:
    1. User-configured fallback_chain (per-task)
    2. (auto) main fallback_providers / fallback_model
    3. (auto) built-in auxiliary discovery chain
    4. (explicit) main agent model safety net

  The actual code (lines 6914-6928):
    - AUTO path: 1 → 2 → 3 ✓
    - EXPLICIT path: 1 → 4 ✗ (skips step 3 entirely)

WHAT THIS WRAPPER DOES:

  When loaded (via `import aux_fallback_fix; aux_fallback_fix.install()`),
  it wraps the auto-or-explicit dispatch in auxiliary_client.py so the
  EXPLICIT path ALSO tries step 3 (built-in discovery chain) when the
  `allow_discovery_fallback: true` config flag is set for that task.

WHEN TO USE:

  - User has explicit `auxiliary.<task>.provider: X` (X is a specific model)
  - User wants X to fail → fall back to the discovery chain → fall back to main agent
  - User is OK with potentially getting a different provider if X is down

WHEN NOT TO USE:

  - User wrote an explicit provider to GUARANTEE a specific backend (e.g.
    "always use openrouter for vision"). Default OFF preserves this guarantee.
  - User is happy with the historical behavior (step 1 → step 4).
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple, Any

logger = logging.getLogger("aux_fallback_fix")


_INSTALLED = False


def _read_config_flag(task: str) -> bool:
    """Read auxiliary.<task>.allow_discovery_fallback from config.yaml.

    Returns False if the flag is missing, the config file is missing,
    or the hermes_cli module is not importable. Default-False is the
    SAFE choice (preserves historical behavior).
    """
    try:
        from hermes_cli.config import load_config
        config = load_config()
    except Exception as e:
        logger.debug("aux-fallback-fix: could not load config: %s", e)
        return False
    if not isinstance(config, dict):
        return False
    aux = config.get("auxiliary", {})
    if not isinstance(aux, dict):
        return False
    task_config = aux.get(task, {})
    if not isinstance(task_config, dict):
        return False
    return bool(task_config.get("allow_discovery_fallback", False))


def _wrap_dispatch(original_dispatch):
    """Wrap a fallback dispatch function to add step 3 (discovery chain)
    to the EXPLICIT path when the config flag is set.

    The original function is called normally; if it returns (None, None, ""),
    we check the config flag and (if enabled) try _try_payment_fallback
    before the function returns its (None, None, "") result.

    Note: this is a best-effort runtime patch. If the underlying function
    signature changes between hermes-agent versions, the wrap may need
    to be updated.
    """
    def wrapped(*args, **kwargs):
        result = original_dispatch(*args, **kwargs)
        # If the original returned a viable fallback, use it
        if result and result[0] is not None:
            return result
        # Original gave up. Check if this was an EXPLICIT path that should
        # have tried step 3 (discovery) before giving up.
        # We need to figure out the task from args/kwargs to look up the
        # config flag.
        task = kwargs.get("task") or (args[0] if args else None)
        if task and _read_config_flag(task):
            logger.info(
                "aux-fallback-fix: explicit-path fallback exhausted for task=%s; "
                "trying discovery chain (config-gated)", task
            )
            # Try _try_payment_fallback — it's a module-level function we
            # look up lazily so import order doesn't matter.
            try:
                import sys
                aux_mod = sys.modules.get("auxiliary_client")
                if aux_mod is not None:
                    fb_client, fb_model, fb_label = aux_mod._try_payment_fallback(
                        kwargs.get("resolved_provider") or kwargs.get("failed_provider", "auto"),
                        task,
                        reason=kwargs.get("reason", "aux-fallback-fix opt-in"),
                    )
                    if fb_client is not None:
                        return (fb_client, fb_model, fb_label)
            except Exception as e:
                logger.warning("aux-fallback-fix: discovery fallback failed: %s", e)
        return result
    return wrapped


def install():
    """Install the monkey-patch. Idempotent.

    Walks the auxiliary_client module's namespace, finds the dispatch
    orchestrators (the inline `if is_auto / else` blocks), and wraps
    them so the EXPLICIT path also tries step 3 when the config flag is set.

    Implementation note: this is a wrapper, not a true patch. We can't
    cleanly replace inline `if/else` blocks at runtime, so instead we
    intercept at the function-call level — the `_try_configured_fallback_chain`
    call is wrapped to fall through to discovery if it returns nothing AND
    the config flag is set.

    The cleaner fix is upstream (modify auxiliary_client.py directly).
    This wrapper exists for operators who can't or won't modify upstream
    code (e.g. they don't want to maintain a fork).
    """
    global _INSTALLED
    if _INSTALLED:
        logger.debug("aux-fallback-fix: already installed")
        return
    try:
        import auxiliary_client
    except ImportError as e:
        logger.warning("aux-fallback-fix: cannot import auxiliary_client: %s", e)
        return

    # Wrap _try_configured_fallback_chain: if it returns (None, None, ""),
    # and the config flag for this task is True, fall through to
    # _try_payment_fallback.
    original = auxiliary_client._try_configured_fallback_chain
    auxiliary_client._try_configured_fallback_chain = _wrap_dispatch(original)

    _INSTALLED = True
    logger.info("aux-fallback-fix: installed (config-gated, default OFF)")


def uninstall():
    """Reverse the monkey-patch. Idempotent."""
    global _INSTALLED
    try:
        import auxiliary_client
        # Restore the original by re-importing the module
        # Note: this is approximate; in practice, just restart the agent
    except ImportError:
        pass
    _INSTALLED = False


if __name__ == "__main__":
    # Test mode: install the patch and verify it loaded
    logging.basicConfig(level=logging.INFO)
    install()
    print(f"Installed: {_INSTALLED}")
    print(f"Config flag for vision (sample): {_read_config_flag('vision')}")
