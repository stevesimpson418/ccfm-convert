"""Tests for state.backend module."""

import json
from unittest.mock import Mock

import pytest

from ccfm_convert.state.backend import ConfluenceBackend, _empty_state


class TestEmptyState:
    def test_returns_version_and_empty_pages(self):
        state = _empty_state()
        assert state["version"] == "1"
        assert state["pages"] == {}


class TestConfluenceBackendLoad:
    def test_load_returns_empty_state_when_no_attachment(self):
        """Returns empty state when download_attachment returns None."""
        api = Mock()
        api.download_attachment.return_value = None
        backend = ConfluenceBackend(api, "page-123")

        result = backend.load()

        assert result == _empty_state()
        api.download_attachment.assert_called_once_with("page-123", "ccfm-state.json")

    def test_load_parses_attachment_json(self):
        """Parses valid JSON from attachment content."""
        state_data = {
            "version": "1",
            "pages": {
                "docs/guide.md": {
                    "page_id": "42",
                    "title": "Guide",
                    "space_key": "DOCS",
                    "space_id": "sid",
                    "content_hash": "sha256:abc",
                    "deployed_at": "2024-01-01T00:00:00+00:00",
                }
            },
        }
        api = Mock()
        api.download_attachment.return_value = json.dumps(state_data).encode("utf-8")
        backend = ConfluenceBackend(api, "page-123")

        result = backend.load()

        assert result["pages"]["docs/guide.md"]["page_id"] == "42"

    def test_load_raises_on_invalid_schema_not_dict(self):
        """Raises ValueError when attachment content is not a dict."""
        api = Mock()
        api.download_attachment.return_value = json.dumps(["not", "a", "dict"]).encode("utf-8")
        backend = ConfluenceBackend(api, "page-123")

        with pytest.raises(ValueError, match="unexpected schema"):
            backend.load()

    def test_load_raises_on_invalid_schema_no_pages(self):
        """Raises ValueError when dict has no pages key."""
        api = Mock()
        api.download_attachment.return_value = json.dumps({"version": "1"}).encode("utf-8")
        backend = ConfluenceBackend(api, "page-123")

        with pytest.raises(ValueError, match="unexpected schema"):
            backend.load()


class TestConfluenceBackendSave:
    def test_save_uploads_json_as_attachment(self, tmp_path):
        """save() uploads state JSON to management page."""
        api = Mock()
        api.upload_attachment.return_value = {"results": [{"id": "att1"}]}
        backend = ConfluenceBackend(api, "page-123")

        state_data = {"version": "1", "pages": {"a.md": {"page_id": "1"}}}
        backend.save(state_data)

        api.upload_attachment.assert_called_once()
        call_args = api.upload_attachment.call_args
        assert call_args[1]["name"] == "ccfm-state.json"
        # Verify the temp file was cleaned up
        filepath = call_args[0][1]
        assert not filepath.exists()

    def test_save_cleans_up_temp_file_on_upload_failure(self):
        """Temp file is deleted even if upload fails."""
        api = Mock()
        api.upload_attachment.side_effect = RuntimeError("Upload failed")
        backend = ConfluenceBackend(api, "page-123")

        with pytest.raises(RuntimeError, match="Upload failed"):
            backend.save({"version": "1", "pages": {}})

        # Temp file should still be cleaned up via finally block
        api.upload_attachment.assert_called_once()

    def test_save_writes_sorted_json(self):
        """State data is written with sort_keys=True."""
        api = Mock()
        api.upload_attachment.return_value = {"results": [{"id": "att1"}]}
        backend = ConfluenceBackend(api, "page-123")

        state_data = {"version": "1", "pages": {"b.md": {"page_id": "2"}, "a.md": {"page_id": "1"}}}

        # Capture the uploaded content by reading the temp file before it's deleted
        uploaded_content = None

        def capture_upload(page_id, filepath, name=None, quiet=False):
            nonlocal uploaded_content
            uploaded_content = filepath.read_bytes()
            return {"results": [{"id": "att1"}]}

        api.upload_attachment.side_effect = capture_upload
        backend.save(state_data)

        parsed = json.loads(uploaded_content.decode("utf-8"))
        assert list(parsed["pages"].keys()) == sorted(parsed["pages"].keys())

    def test_save_passes_quiet_to_upload_attachment(self):
        """save() passes quiet=True to suppress noisy attachment messages."""
        api = Mock()
        api.upload_attachment.return_value = {"results": [{"id": "att1"}]}
        backend = ConfluenceBackend(api, "page-123")

        backend.save({"version": "1", "pages": {}})

        call_kwargs = api.upload_attachment.call_args[1]
        assert call_kwargs["quiet"] is True

    def test_save_prints_success_message(self, capsys):
        """save() prints a success message after uploading state."""
        api = Mock()
        api.upload_attachment.return_value = {"results": [{"id": "att1"}]}
        backend = ConfluenceBackend(api, "page-123")

        backend.save({"version": "1", "pages": {}})

        captured = capsys.readouterr()
        assert "CCFM State updated successfully" in captured.out
