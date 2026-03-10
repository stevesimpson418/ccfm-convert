"""Smoke tests: directory deployment via --directory."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

EXAMPLE_DIR = SMOKE_DOCS / "example"


class TestDirectoryDeploy:
    """Deploy an entire directory tree and verify all pages deploy successfully."""

    def test_tree_creates_all_pages(self, ccfm_run, confluence_live):
        """deploy --directory deploys all markdown files."""
        result = ccfm_run("deploy", "--directory", str(EXAMPLE_DIR))

        assert result.returncode == 0, f"Directory deploy failed:\n{result.stderr}"
        # Should mention creating or updating pages
        assert "Creating" in result.stdout or "Updating" in result.stdout

    def test_plan_shows_no_ops_after_deploy(self, ccfm_run, confluence_live):
        """deploy --plan after a full deploy reports NO-OP for all pages and exits 0."""
        result = ccfm_run("deploy", "--plan", "--directory", str(EXAMPLE_DIR), check=False)

        assert result.returncode == 0, (
            f"--plan after deploy should exit 0 (all NO-OP), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "NO-OP" in result.stdout
        ), f"Expected 'NO-OP' in --plan output after deploy.\nstdout: {result.stdout}"
