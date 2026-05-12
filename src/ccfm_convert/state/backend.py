"""State storage backends for CCFM deployments."""

import hashlib
import re
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ccfm_convert.deploy.api import ConfluenceAPI

STATE_VERSION = "1"

# Each tracked page is stored as a content property on the management page.
# Key format: ``ccfm-page-<sha256(path)[:16]>`` — 26 chars, ``[a-z0-9-]``
# (a strict subset of Atlassian's allowed key pattern ``^[a-zA-Z0-9_-]+$``).
PAGE_PROPERTY_PREFIX = "ccfm-page-"
_PAGE_KEY_RE = re.compile(rf"^{re.escape(PAGE_PROPERTY_PREFIX)}[0-9a-f]{{16}}$")


class StateBackend(Protocol):
    """Protocol for state storage backends.

    Implementations must provide load() and save() for persisting state data.
    The protocol exists for future extensibility (e.g. an S3 backend).
    """

    def load(self) -> dict:
        """Load state data. Returns empty state dict if no state exists."""
        ...

    def save(self, data: dict) -> None:
        """Persist state data."""
        ...


def _empty_state() -> dict:
    """Return a fresh empty state structure."""
    return {"version": STATE_VERSION, "pages": {}}


def _key_for_path(rel_path: str) -> str:
    """Derive a deterministic content-property key from a relative path."""
    digest = hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:16]
    return f"{PAGE_PROPERTY_PREFIX}{digest}"


class ContentPropertyBackend:
    """Stores state as per-page content properties on the CCFM management page.

    Each tracked page becomes one content property keyed by a deterministic
    hash of its relative path. The property value carries the page's metadata
    plus the path (so ``load`` can reconstruct the path → entry mapping). The
    lock property (``ccfm-lock``) is owned by ``LockManager`` and is ignored
    by this backend.

    Each entry stays well under the per-property 32 KB payload limit, and
    Confluence imposes no documented hard cap on the count of properties per
    content item — capacity therefore scales with the number of tracked pages
    rather than being bounded by a single 32 KB blob.
    """

    def __init__(self, api: "ConfluenceAPI", page_id: str) -> None:
        self._api = api
        self._page_id = page_id
        # Populated by load(): {property_key: {"value": dict, "version": int}}.
        # save() reads this to (a) skip writes for entries whose value is
        # unchanged, and (b) PUT with version+1 only the entries that actually
        # changed. The cache is meaningful only for the duration of a single
        # load → save cycle and only when the caller holds the state lock —
        # callers that need fresh versions (e.g. ``state push``, where the
        # input is arbitrary user data) should call ``load`` again *inside*
        # the lock. See the comment in ``main._handle_state`` for context.
        self._cache: dict[str, dict] = {}

    def load(self) -> dict:
        """Read all per-page properties from the management page."""
        self._cache = {}
        pages: dict = {}
        for prop in self._api.list_content_properties(self._page_id):
            key = prop.get("key", "")
            if not _PAGE_KEY_RE.match(key):
                continue
            value = prop.get("value")
            if not isinstance(value, dict):
                raise ValueError(
                    f"State property '{key}' has unexpected value type (page_id={self._page_id})"
                )
            path = value.get("path")
            if not isinstance(path, str) or not path:
                raise ValueError(
                    f"State property '{key}' is missing a string 'path' (page_id={self._page_id})"
                )
            version_number = prop.get("version", {}).get("number")
            if not isinstance(version_number, int):
                # Without a numeric version we cannot issue PUT-with-version on
                # the next save(). Refuse to load rather than silently dropping
                # the entry from the cache — a missing entry would be
                # mis-classified as "new" on the next save() and POST'd, which
                # Confluence rejects (the property already exists). Better to
                # surface the malformed envelope here than to mask it as a
                # confusing 4xx from set_content_property later.
                raise ValueError(
                    f"State property '{key}' is missing a numeric 'version.number' "
                    f"(page_id={self._page_id})"
                )
            entry = {k: v for k, v in value.items() if k != "path"}
            pages[path] = entry
            self._cache[key] = {"value": value, "version": version_number}
        return {"version": STATE_VERSION, "pages": pages}

    def save(self, data: dict) -> None:
        """Persist state by reconciling per-page properties with ``data``.

        Diffs the incoming pages dict against the cache populated by ``load``:
        unchanged entries are skipped (no API call), changed entries become a
        PUT with version+1, new entries become a POST, and removed entries
        become a DELETE. Callers must hold the state lock.
        """
        # Require the "pages" key explicitly. If we defaulted to {} when absent
        # and the cache contained entries, save() would silently delete every
        # tracked page — that's a destructive operation that should never
        # happen by accident (e.g. from a state-push of a malformed file).
        if "pages" not in data:
            raise ValueError("State data must contain a 'pages' key")
        pages = data["pages"]
        if not isinstance(pages, dict):
            raise ValueError("State data 'pages' must be a dict")

        new_keys: set[str] = set()
        for path, entry in pages.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"State entry for '{path}' is not a dict (got {type(entry).__name__})"
                )
            if "path" in entry:
                # The relative path is the dict key — duplicating it inside the
                # entry is ambiguous (which one wins?) and most often signals a
                # caller that round-tripped a loaded value back into save()
                # without stripping the synthesised 'path' field. Refuse rather
                # than risk corrupting the path → entry mapping on the next load.
                raise ValueError(f"State entry for '{path}' must not contain its own 'path' key")
            key = _key_for_path(path)
            new_keys.add(key)
            value = {"path": path, **entry}
            cached = self._cache.get(key)
            if cached is None:
                self._api.set_content_property(self._page_id, key, value)
            elif cached["value"] != value:
                self._api.set_content_property(
                    self._page_id, key, value, version=cached["version"] + 1
                )
            # else: value identical — skip the write entirely.

        for key in set(self._cache) - new_keys:
            self._api.delete_content_property(self._page_id, key)

        # Reset the cache so any subsequent save() in the same process must be
        # preceded by an explicit load(). Without the reset, cached version
        # numbers are stale — we don't know what Confluence assigned during
        # the writes above. Without a follow-up load(), a second save() would
        # mis-classify existing entries as new and POST them, which Confluence
        # rejects.
        self._cache = {}
        print("   ✅ CCFM State updated successfully")
