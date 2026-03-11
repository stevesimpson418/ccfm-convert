"""CCFM state manager — persists filepath -> page_id mappings between deployments."""

import copy
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from ccfm_convert.state.backend import StateBackend


class StateManager:
    """Tracks deployed pages across runs via a remote state backend.

    The state maps relative file paths (from the working directory) to their
    Confluence page metadata, enabling changed-files-only deployment, orphan detection,
    and plan/diff mode.
    """

    STATE_VERSION = "1"

    def __init__(self, backend: StateBackend) -> None:
        self._backend = backend
        self._state: dict = {"version": self.STATE_VERSION, "pages": {}}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load state from the backend."""
        self._state = self._backend.load()

    def save(self) -> None:
        """Persist state via the backend."""
        self._backend.save(self._state)

    # ------------------------------------------------------------------
    # Page records
    # ------------------------------------------------------------------

    def get_page(self, rel_path: str) -> dict | None:
        """Return the state entry for a relative path, or None if not tracked."""
        return self._state["pages"].get(rel_path)

    def set_page(
        self,
        rel_path: str,
        page_id: str,
        title: str,
        space_key: str,
        space_id: str,
        content_hash: str,
    ) -> None:
        """Create or update the state entry for a deployed page."""
        self._state["pages"][rel_path] = {
            "page_id": page_id,
            "title": title,
            "space_key": space_key,
            "space_id": space_id,
            "content_hash": content_hash,
            "deployed_at": datetime.now(UTC).isoformat(),
        }

    def remove_page(self, rel_path: str) -> None:
        """Remove a page entry (called after destroying a page)."""
        self._state["pages"].pop(rel_path, None)

    @property
    def all_pages(self) -> dict:
        """Return a deep copy of all page entries keyed by relative path."""
        return copy.deepcopy(self._state["pages"])

    @property
    def raw_state(self) -> dict:
        """Return a deep copy of the full state dict (version + pages).

        A deep copy prevents callers from accidentally mutating internal state
        through the returned pages dict.
        """
        return copy.deepcopy(self._state)

    # ------------------------------------------------------------------
    # Content hashing
    # ------------------------------------------------------------------

    def compute_hash(self, filepath: Path) -> str:
        """Return a SHA-256 hex digest of the file's contents.

        The hash is prefixed with 'sha256:' for future algorithm flexibility.
        """
        digest = hashlib.sha256(filepath.read_bytes()).hexdigest()
        return f"sha256:{digest}"

    def has_changed(self, rel_path: str, filepath: Path) -> bool:
        """Return True if the file content differs from the stored hash, or if
        the file has never been deployed (not in state)."""
        entry = self.get_page(rel_path)
        if entry is None:
            return True
        return entry["content_hash"] != self.compute_hash(filepath)

    # ------------------------------------------------------------------
    # Orphan detection
    # ------------------------------------------------------------------

    def find_orphans(self, current_files: list[Path], docs_root: Path) -> list[str]:
        """Return relative paths that are tracked in state but have no corresponding
        file on disk within docs_root.

        An orphan means the markdown source was deleted — the Confluence page will
        be destroyed on the next ``ccfm apply``.

        docs_root may be absolute or relative; it is normalised to a relative path
        from cwd so comparisons against stored rel_paths are consistent.
        """

        def _to_rel(f: Path) -> str:
            try:
                return str(f.relative_to(Path.cwd()))
            except ValueError:
                return str(f)

        # Normalise docs_root to relative-from-cwd so it matches stored rel_paths
        try:
            docs_root_rel = docs_root.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            docs_root_rel = docs_root

        current_rel = {_to_rel(f) for f in current_files}
        orphans = []
        for rel_path in self._state["pages"]:
            # Skip directory container pages (no .md extension) — they are not files on disk
            if not rel_path.endswith(".md"):
                continue
            # Only flag orphans that were under the docs_root being deployed
            try:
                Path(rel_path).relative_to(docs_root_rel)
            except ValueError:
                continue
            if rel_path not in current_rel:
                orphans.append(rel_path)
        return orphans
