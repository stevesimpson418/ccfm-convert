"""CCFM state manager — persists filepath → page_id mappings between deployments."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


class StateManager:
    """Tracks deployed pages across runs via a local JSON state file.

    The state file maps relative file paths (from the working directory) to their
    Confluence page metadata, enabling changed-files-only deployment, orphan detection,
    and plan/diff mode.

    The state file is intended to be committed alongside documentation so that CI
    pipelines and team members share the same deployment history.
    """

    STATE_VERSION = "1"

    def __init__(self, path: Path):
        self.path = path
        self._state: dict = {"version": self.STATE_VERSION, "pages": {}}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load state from disk. Silent no-op if the file does not exist."""
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("pages"), dict):
            raise ValueError(f"State file has unexpected schema: {self.path}")
        self._state = data

    def save(self) -> None:
        """Atomically write state to disk (write-then-rename).

        Creates parent directories if they do not exist. The temporary file is
        written with mode 0o600 (owner read/write only) to avoid exposing space
        IDs and page titles to other users on shared systems.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        payload = json.dumps(self._state, indent=2, sort_keys=True)
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        tmp.rename(self.path)

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
        """Remove a page entry (called after archiving an orphaned page)."""
        self._state["pages"].pop(rel_path, None)

    @property
    def all_pages(self) -> dict:
        """Return a shallow copy of all page entries keyed by relative path."""
        return dict(self._state["pages"])

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

        An orphan means the markdown source was deleted — the Confluence page may
        need to be archived.

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
            # Only flag orphans that were under the docs_root being deployed
            try:
                Path(rel_path).relative_to(docs_root_rel)
            except ValueError:
                continue
            if rel_path not in current_rel:
                orphans.append(rel_path)
        return orphans
