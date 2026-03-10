"""Terraform-style locking for CCFM remote state."""

import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ccfm_convert.deploy.api import ConfluenceAPI

LOCK_PROPERTY_KEY = "ccfm-lock"


class LockError(Exception):
    """Raised when a lock cannot be acquired."""


@dataclass
class LockInfo:
    """Information about the current lock state."""

    locked: bool
    owner: str = ""
    lock_id: str = ""
    locked_at: str = ""
    operation: str = ""
    version: int | None = None


def _default_owner() -> str:
    """Return a default lock owner identifier: user@hostname."""
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    return f"{user}@{socket.gethostname()}"


class LockManager:
    """Manages distributed locking via Confluence content properties.

    Uses optimistic concurrency: reads the property version, then writes with
    that version. If another process modified the property between read and
    write, Confluence returns 409 Conflict.
    """

    def __init__(self, api: "ConfluenceAPI", page_id: str) -> None:
        self._api = api
        self._page_id = page_id

    def status(self) -> LockInfo:
        """Return the current lock status."""
        prop = self._api.get_content_property(self._page_id, LOCK_PROPERTY_KEY)
        if prop is None:
            return LockInfo(locked=False)
        val = prop.get("value", {})
        return LockInfo(
            locked=val.get("locked", False),
            owner=val.get("owner", ""),
            lock_id=val.get("lock_id", ""),
            locked_at=val.get("locked_at", ""),
            operation=val.get("operation", ""),
            version=prop.get("version", {}).get("number"),
        )

    def acquire(self, operation: str = "deploy", lock_id: str | None = None) -> None:
        """Acquire the lock. Raises LockError if already held."""
        info = self.status()
        if info.locked:
            raise LockError(
                f"State is locked by {info.owner}"
                + (f" (lock_id: {info.lock_id})" if info.lock_id else "")
                + f" since {info.locked_at}"
                + f" (operation: {info.operation})."
                + " Run `ccfm lock release` to force-unlock."
            )
        owner = _default_owner()
        value = {
            "locked": True,
            "owner": owner,
            "lock_id": lock_id or "",
            "locked_at": datetime.now(UTC).isoformat(),
            "operation": operation,
        }
        try:
            self._api.set_content_property(
                self._page_id,
                LOCK_PROPERTY_KEY,
                value,
                version=info.version + 1 if info.version is not None else None,
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                raise LockError("Lock was acquired by another process (version conflict).") from exc
            raise

    def release(self) -> None:
        """Release the lock. No-op if the property doesn't exist.

        Confluence returns 403 (not 404) when DELETE is called on a content
        property that has never been created, so we must guard with a GET first.
        """
        if self._api.get_content_property(self._page_id, LOCK_PROPERTY_KEY) is None:
            return
        self._api.delete_content_property(self._page_id, LOCK_PROPERTY_KEY)

    def force_release(self) -> None:
        """Force-release the lock regardless of owner."""
        self.release()
