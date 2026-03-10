"""Smoke tests: single-file deployment via --file."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

SINGLE_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"


class TestSingleFileDeploy:
    """Deploy a single markdown file and verify it deploys successfully."""

    def test_page_created(self, ccfm_run, confluence_live):
        """deploy --file deploys successfully."""
        result = ccfm_run("deploy", "--file", str(SINGLE_PAGE))

        assert result.returncode == 0, f"Deploy failed:\n{result.stderr}"
        assert (
            "Success" in result.stdout or "Updating" in result.stdout or "Creating" in result.stdout
        )

    def test_page_updated_on_redeploy(self, ccfm_run, confluence_live):
        """Re-deploying the same file updates (not duplicates) the page."""
        # First deploy
        ccfm_run("deploy", "--file", str(SINGLE_PAGE))

        # Second deploy should update
        result = ccfm_run("deploy", "--file", str(SINGLE_PAGE))
        assert result.returncode == 0
        assert "Updating" in result.stdout, "Expected 'Updating' in output for a re-deploy"

    def test_dump_mode_writes_adf(self, ccfm_run):
        """deploy --dump writes an .adf.json file locally without API calls."""
        adf_file = SINGLE_PAGE.with_suffix(".adf.json")
        adf_file.unlink(missing_ok=True)

        result = ccfm_run("deploy", "--file", str(SINGLE_PAGE), "--dump")
        assert result.returncode == 0
        assert adf_file.exists(), ".adf.json file was not written by --dump"

        # Cleanup the generated file
        adf_file.unlink(missing_ok=True)
