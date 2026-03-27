"""State storage backends for CCFM deployments."""

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ccfm_convert.deploy.api import ConfluenceAPI

STATE_VERSION = "1"


class StateBackend(Protocol):
    """Protocol for state storage backends.

    Implementations must provide load() and save() for persisting state data.
    The protocol exists for future extensibility (e.g. S3 backend).
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


class ConfluenceBackend:
    """Stores state as an attachment on the CCFM management page in Confluence."""

    STATE_ATTACHMENT_NAME = "ccfm-state.json"

    def __init__(self, api: "ConfluenceAPI", page_id: str) -> None:
        self._api = api
        self._page_id = page_id

    def load(self) -> dict:
        """Download state from the management page attachment."""
        content = self._api.download_attachment(self._page_id, self.STATE_ATTACHMENT_NAME)
        if content is None:
            return _empty_state()
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("pages"), dict):
            raise ValueError(
                f"Remote state attachment has unexpected schema (page_id={self._page_id})"
            )
        return data

    def save(self, data: dict) -> None:
        """Upload state as a JSON attachment to the management page."""
        payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".json", prefix="ccfm-state-", delete=False) as fh:
            fh.write(payload)
            tmp_path = Path(fh.name)
        try:
            self._api.upload_attachment(
                self._page_id, tmp_path, name=self.STATE_ATTACHMENT_NAME, quiet=True
            )
            print("   ✅ CCFM State updated successfully")
        finally:
            tmp_path.unlink(missing_ok=True)
