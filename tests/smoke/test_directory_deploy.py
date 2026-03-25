"""Smoke tests: docs_root deployment."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke


class TestDocsRootDeploy:
    """Deploy the full docs_root tree and verify all pages deploy successfully."""

    def test_tree_creates_all_pages(self, ccfm_run, confluence_live):
        """apply deploys all markdown files from docs_root."""
        result = ccfm_run("apply", "--auto-approve", "--docs-root", str(SMOKE_DOCS))

        assert result.returncode == 0, f"Apply failed:\n{result.stderr}"
        # Should mention creating or updating pages
        assert "Creating" in result.stdout or "Updating" in result.stdout

    def test_plan_shows_no_changes_after_apply(self, ccfm_run, confluence_live):
        """plan after a full apply reports no changes and exits 0."""
        result = ccfm_run("plan", "--docs-root", str(SMOKE_DOCS), check=False)

        assert result.returncode == 0, (
            f"plan after apply should exit 0 (no changes), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "No changes" in result.stdout or "unchanged" in result.stdout
        ), f"Expected no-changes message in plan output after apply.\nstdout: {result.stdout}"
