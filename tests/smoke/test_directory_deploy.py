"""Smoke tests: directory deployment via --directory."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

EXAMPLE_DIR = SMOKE_DOCS / "example"


class TestDirectoryDeploy:
    """Deploy an entire directory tree and verify all pages deploy successfully."""

    def test_tree_creates_all_pages(self, ccfm_run, confluence_live):
        """apply --directory deploys all markdown files."""
        result = ccfm_run("apply", "--auto-approve", "--directory", str(EXAMPLE_DIR))

        assert result.returncode == 0, f"Directory apply failed:\n{result.stderr}"
        # Should mention creating or updating pages
        assert "Creating" in result.stdout or "Updating" in result.stdout

    def test_plan_shows_no_changes_after_apply(self, ccfm_run, confluence_live):
        """plan after a full apply reports no changes and exits 0."""
        result = ccfm_run("plan", "--directory", str(EXAMPLE_DIR), check=False)

        assert result.returncode == 0, (
            f"plan after apply should exit 0 (no changes), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "No changes" in result.stdout or "unchanged" in result.stdout
        ), f"Expected no-changes message in plan output after apply.\nstdout: {result.stdout}"
