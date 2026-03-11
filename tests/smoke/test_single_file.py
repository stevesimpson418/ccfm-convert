"""Smoke tests: single-file deployment and dump subcommand."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

SINGLE_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"
COMPLETE_EXAMPLE = SMOKE_DOCS / "example" / "CCFM Example" / "complete_example.md"


class TestSingleFileDeploy:
    """Deploy a single markdown file and verify it deploys successfully."""

    def test_page_created(self, ccfm_run, confluence_live):
        """apply --file deploys successfully."""
        result = ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        assert result.returncode == 0, f"Apply failed:\n{result.stderr}"
        assert (
            "Success" in result.stdout or "Updating" in result.stdout or "Creating" in result.stdout
        )

    def test_page_updated_on_force_reapply(self, ccfm_run, confluence_live):
        """Re-applying with --force updates (not duplicates) the page."""
        # First apply
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        # Second apply with --force should re-deploy even though content is unchanged
        result = ccfm_run("apply", "--auto-approve", "--force", "--file", str(SINGLE_PAGE))
        assert result.returncode == 0
        assert "Updating" in result.stdout, "Expected 'Updating' in output for a --force re-apply"

    def test_reapply_unchanged_is_noop(self, ccfm_run, confluence_live):
        """Re-applying an unchanged file is a no-op (change detection)."""
        # First apply
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        # Second apply without --force should detect no changes
        result = ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))
        assert result.returncode == 0
        assert "No changes" in result.stdout, "Expected no-op on unchanged re-apply"

    def test_dump_writes_adf(self, ccfm_run, tmp_path):
        """dump --file writes an .adf.json file to the output directory."""
        output_dir = tmp_path / "dump-output"

        result = ccfm_run("dump", "--file", str(SINGLE_PAGE), "--output-dir", str(output_dir))
        assert result.returncode == 0
        assert "Dump complete" in result.stdout

        # Verify at least one .adf.json file was created
        adf_files = list(output_dir.rglob("*.adf.json"))
        assert len(adf_files) > 0, "No .adf.json files found in dump output directory"

    def test_dump_directory(self, ccfm_run, tmp_path):
        """dump --directory writes .adf.json for all files without API calls."""
        output_dir = tmp_path / "dump-dir-output"

        result = ccfm_run("dump", "--directory", str(SMOKE_DOCS), "--output-dir", str(output_dir))
        assert result.returncode == 0
        assert "Dump complete" in result.stdout

        adf_files = list(output_dir.rglob("*.adf.json"))
        assert len(adf_files) >= 5, f"Expected at least 5 .adf.json files, got {len(adf_files)}"

    def test_dump_with_page_links_no_crash(self, ccfm_run, tmp_path):
        """dump mode doesn't crash on files with confluence_page:// links.

        Regression test: the old --dump flag crashed with NoneType error on
        complete_example.md because resolve_page_links() was called with api=None.
        The new dump subcommand skips page link resolution entirely.
        """
        output_dir = tmp_path / "dump-links-output"

        result = ccfm_run("dump", "--file", str(COMPLETE_EXAMPLE), "--output-dir", str(output_dir))
        assert result.returncode == 0, f"Dump crashed on page links file:\n{result.stderr}"
        assert "Dump complete" in result.stdout
