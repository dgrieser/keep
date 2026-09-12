"""Building an authenticated :class:`gkeepapi.Keep` instance."""

from __future__ import annotations

import logging

import gkeepapi
from gkeepapi import exception as gexc

from . import config as cfgmod

log = logging.getLogger(__name__)


class KeepError(Exception):
    """User-facing failure while talking to Google Keep."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def open_keep(cfg: cfgmod.Config | None = None, *, use_cache: bool = True) -> gkeepapi.Keep:
    """Return a synced ``Keep`` instance for the configured account.

    Cached state is used when available so that only an incremental sync is needed.
    """
    try:
        cfg = cfg or cfgmod.load_config()
    except cfgmod.ConfigError as exc:
        raise KeepError(str(exc)) from exc

    keep = gkeepapi.Keep()
    state = cfgmod.load_state() if use_cache else None
    try:
        try:
            keep.authenticate(cfg.email, cfg.master_token, state=state, device_id=cfg.device_id)
        except gexc.ResyncRequiredException:
            log.info("cached state is stale; performing a full resync")
            keep = gkeepapi.Keep()
            keep.authenticate(cfg.email, cfg.master_token, state=None, device_id=cfg.device_id)
    except gexc.LoginException as exc:
        raise KeepError(
            f"Authentication failed for {cfg.email}: {exc}. Run `keep login` to re-authorize."
        ) from exc
    except gexc.KeepException as exc:
        raise KeepError(f"Google Keep error: {exc}") from exc

    if use_cache:
        persist(keep)
    return keep


def persist(keep: gkeepapi.Keep) -> None:
    """Save the current Keep state to the cache. Failures are non-fatal."""
    try:
        cfgmod.save_state(keep.dump())
    except OSError as exc:
        log.warning("could not write state cache: %s", exc)


def commit(keep: gkeepapi.Keep) -> None:
    """Push local modifications to Google and refresh the cache."""
    try:
        keep.sync()
    except gexc.ResyncRequiredException:
        keep.sync(resync=True)
    except gexc.KeepException as exc:
        raise KeepError(f"Sync failed: {exc}") from exc
    persist(keep)


def verify_credentials(cfg: cfgmod.Config) -> None:
    """Authenticate once without syncing, to validate a freshly obtained token."""
    keep = gkeepapi.Keep()
    try:
        keep.authenticate(cfg.email, cfg.master_token, sync=False, device_id=cfg.device_id)
    except gexc.LoginException as exc:
        raise KeepError(f"Authentication failed: {exc}") from exc
    except gexc.KeepException as exc:
        raise KeepError(f"Google Keep error: {exc}") from exc
