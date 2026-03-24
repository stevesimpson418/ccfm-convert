"""Smoke tests: --debug-file ADF inspection."""

import json

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

SINGLE_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"
COMPLETE_EXAMPLE = SMOKE_DOCS / "example" / "CCFM Example" / "complete_example.md"


class TestDebugFile:
    """Test --debug-file prints valid ADF JSON to stdout."""

    def test_debug_file_outputs_valid_adf(self, ccfm_run):
        """plan --debug-file prints valid ADF JSON to stdout."""
        result = ccfm_run("plan", "--debug-file", str(SINGLE_PAGE))
        assert result.returncode == 0, f"Debug-file failed:\n{result.stderr}"

        data = json.loads(result.stdout)
        assert data["type"] == "doc"
        assert "content" in data

    def test_debug_file_with_page_links_no_crash(self, ccfm_run):
        """--debug-file doesn't crash on files with confluence_page:// links."""
        result = ccfm_run("plan", "--debug-file", str(COMPLETE_EXAMPLE))
        assert result.returncode == 0, f"Debug-file crashed on page links file:\n{result.stderr}"

        data = json.loads(result.stdout)
        assert data["type"] == "doc"

    def test_debug_file_no_credentials_needed(self, ccfm_run):
        """--debug-file does not require API credentials."""
        result = ccfm_run("plan", "--debug-file", str(SINGLE_PAGE))
        assert result.returncode == 0
