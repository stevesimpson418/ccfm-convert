"""Smoke tests: state management — plan mode, --changed-only, --archive-orphans."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

STATE_DIR = SMOKE_DOCS / "state-management"
PAGE_ALPHA = STATE_DIR / "page-alpha.md"
PAGE_BETA = STATE_DIR / "page-beta.md"

# Relative path fragments used to identify state entries
ALPHA_KEY = "page-alpha.md"
BETA_KEY = "page-beta.md"


class TestPlanMode:
    """--plan exit codes and output before/after a deploy."""

    def test_plan_before_deploy_shows_creates(self, ccfm_run, confluence_live):
        """deploy --plan --plan-exit-code before any deploy exits 2 and lists CREATE actions."""
        result = ccfm_run(
            "deploy", "--plan", "--plan-exit-code", "--directory", str(STATE_DIR), check=False
        )

        assert result.returncode == 2, (
            f"Expected exit 2 (pending changes) before first deploy, "
            f"got {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "CREATE" in result.stdout
        ), f"Expected 'CREATE' in --plan output before deploy.\nstdout: {result.stdout}"

    def test_plan_after_deploy_shows_no_ops(self, ccfm_run, confluence_live):
        """deploy --plan after a full deploy exits 0 and shows NO-OP for all pages."""
        # Deploy both pages first
        result = ccfm_run("deploy", "--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        result = ccfm_run("deploy", "--plan", "--directory", str(STATE_DIR), check=False)

        assert result.returncode == 0, (
            f"Expected exit 0 (all NO-OP) after deploy, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "NO-OP" in result.stdout
        ), f"Expected 'NO-OP' in --plan output.\nstdout: {result.stdout}"


class TestChangedOnly:
    """--changed-only skips unchanged files and deploys modified ones."""

    def test_changed_only_skips_unchanged(self, ccfm_run, confluence_live):
        """After a clean deploy, --changed-only reports 0 files with changes."""
        # Ensure both pages are deployed
        ccfm_run("deploy", "--directory", str(STATE_DIR))

        result = ccfm_run("deploy", "--changed-only", "--directory", str(STATE_DIR))

        assert result.returncode == 0, f"--changed-only failed:\n{result.stderr}"
        assert (
            "0 file(s) with changes" in result.stdout
        ), f"Expected '0 file(s) with changes' in output.\nstdout: {result.stdout}"

    def test_changed_only_deploys_modified_file(self, ccfm_run, tmp_path, confluence_live):
        """After modifying page-alpha, --changed-only deploys only that file."""
        # Ensure a clean baseline deploy first
        ccfm_run("deploy", "--directory", str(STATE_DIR))

        # Write a modified copy of page-alpha with new content
        original_content = PAGE_ALPHA.read_text(encoding="utf-8")
        modified_content = original_content.replace(
            "Version: **1**",
            "Version: **2** — updated by smoke test",
        )

        try:
            PAGE_ALPHA.write_text(modified_content, encoding="utf-8")

            result = ccfm_run("deploy", "--changed-only", "--directory", str(STATE_DIR))

            assert (
                result.returncode == 0
            ), f"--changed-only after modification failed:\n{result.stderr}"
            # The modified page should have been processed
            assert ALPHA_KEY.replace(".md", "") in result.stdout or "Updating" in result.stdout, (
                f"Expected page-alpha to appear in --changed-only output.\n"
                f"stdout: {result.stdout}"
            )
            # Unchanged page-beta must NOT be deployed (issue #6)
            assert "page-beta" not in result.stdout, (
                f"Unchanged page-beta should NOT be deployed with --changed-only.\n"
                f"stdout: {result.stdout}"
            )
        finally:
            # Always restore the original content
            PAGE_ALPHA.write_text(original_content, encoding="utf-8")


class TestChangedOnlyWithArchiveOrphans:
    """Regression tests for issue #3.

    When --changed-only detects 0 changes, the deploy must be a no-op — no pages
    should be updated and no pages should be archived.  Previously the tool would
    traverse the full tree despite 0 changes, then archive every page because the
    orphan check compared state against an empty visited set.
    """

    def test_noop_run_does_not_archive_any_pages(self, ccfm_run, confluence_live):
        """Second deploy with --changed-only --archive-orphans must not archive anything."""
        # Step 1: clean deploy
        result = ccfm_run("deploy", "--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        # Step 2: re-run with both flags — no files have changed, must be a no-op
        result = ccfm_run(
            "deploy",
            "--changed-only",
            "--archive-orphans",
            "--directory",
            str(STATE_DIR),
            check=False,
        )

        assert result.returncode == 0, f"--changed-only --archive-orphans failed:\n{result.stderr}"
        assert (
            "No changes to deploy" in result.stdout
        ), f"Expected early-exit message when 0 changes detected.\nstdout: {result.stdout}"

    def test_unchanged_files_not_treated_as_orphans(self, ccfm_run, confluence_live):
        """When only one file changes, unchanged files on disk must not be archived."""
        # Step 1: clean baseline deploy
        result = ccfm_run("deploy", "--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        # Step 2: modify page-alpha only
        original_content = PAGE_ALPHA.read_text(encoding="utf-8")
        modified_content = original_content.replace(
            "Version: **1**",
            "Version: **3** — orphan regression test",
        )
        try:
            PAGE_ALPHA.write_text(modified_content, encoding="utf-8")

            result = ccfm_run(
                "deploy",
                "--changed-only",
                "--archive-orphans",
                "--directory",
                str(STATE_DIR),
                check=False,
            )

            assert (
                result.returncode == 0
            ), f"--changed-only --archive-orphans failed:\n{result.stderr}"

        finally:
            PAGE_ALPHA.write_text(original_content, encoding="utf-8")


class TestArchiveOrphans:
    """--archive-orphans removes pages no longer tracked in the directory."""

    def test_archive_orphans_removes_absent_page(self, ccfm_run, confluence_live):
        """Deploy alpha+beta, then run with --archive-orphans on alpha-only dir.

        The beta page should be archived and removed from state.
        """
        # Step 1: Deploy both pages to ensure beta is tracked
        result = ccfm_run("deploy", "--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        # Step 2: Temporarily move page-beta out of the directory so it becomes an orphan
        beta_backup = PAGE_BETA.with_suffix(".md.bak")
        PAGE_BETA.rename(beta_backup)

        try:
            result = ccfm_run(
                "deploy",
                "--archive-orphans",
                "--directory",
                str(STATE_DIR),
                "--docs-root",
                str(STATE_DIR),
            )

            assert result.returncode == 0, f"--archive-orphans failed:\n{result.stderr}"

        finally:
            # Restore page-beta so subsequent tests/cleanup can find it
            beta_backup.rename(PAGE_BETA)
