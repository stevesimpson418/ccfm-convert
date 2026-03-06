"""Smoke tests: state management — plan mode, --changed-only, --archive-orphans."""

import json

import pytest

from tests.smoke.conftest import SMOKE_DOCS, SMOKE_STATE

pytestmark = pytest.mark.smoke

STATE_DIR = SMOKE_DOCS / "state-management"
PAGE_ALPHA = STATE_DIR / "page-alpha.md"
PAGE_BETA = STATE_DIR / "page-beta.md"

# Relative path fragments used to identify state entries
ALPHA_KEY = "page-alpha.md"
BETA_KEY = "page-beta.md"


class TestPlanMode:
    """--plan exit codes and output before/after a deploy."""

    def test_plan_before_deploy_shows_creates(self, ccfm_run):
        """--plan --plan-exit-code before any deploy exits 2 and lists CREATE actions."""
        # Ensure no pre-existing state for this directory
        SMOKE_STATE.unlink(missing_ok=True)

        result = ccfm_run("--plan", "--plan-exit-code", "--directory", str(STATE_DIR), check=False)

        assert result.returncode == 2, (
            f"Expected exit 2 (pending changes) before first deploy, "
            f"got {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "CREATE" in result.stdout
        ), f"Expected 'CREATE' in --plan output before deploy.\nstdout: {result.stdout}"

    def test_plan_after_deploy_shows_no_ops(self, ccfm_run, confluence_live):
        """--plan after a full deploy exits 0 and shows NO-OP for all pages."""
        # Deploy both pages first
        result = ccfm_run("--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        result = ccfm_run("--plan", "--directory", str(STATE_DIR), check=False)

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
        # Ensure both pages are deployed (may already be from TestPlanMode)
        ccfm_run("--directory", str(STATE_DIR))

        result = ccfm_run("--changed-only", "--directory", str(STATE_DIR))

        assert result.returncode == 0, f"--changed-only failed:\n{result.stderr}"
        assert (
            "0 file(s) with changes" in result.stdout
        ), f"Expected '0 file(s) with changes' in output.\nstdout: {result.stdout}"

    def test_changed_only_deploys_modified_file(self, ccfm_run, tmp_path, confluence_live):
        """After modifying page-alpha, --changed-only deploys only that file."""
        # Ensure a clean baseline deploy first
        ccfm_run("--directory", str(STATE_DIR))

        # Write a modified copy of page-alpha with new content
        original_content = PAGE_ALPHA.read_text(encoding="utf-8")
        modified_content = original_content.replace(
            "Version: **1**",
            "Version: **2** — updated by smoke test",
        )

        try:
            PAGE_ALPHA.write_text(modified_content, encoding="utf-8")

            result = ccfm_run("--changed-only", "--directory", str(STATE_DIR))

            assert (
                result.returncode == 0
            ), f"--changed-only after modification failed:\n{result.stderr}"
            # The modified page should have been processed
            assert ALPHA_KEY.replace(".md", "") in result.stdout or "Updating" in result.stdout, (
                f"Expected page-alpha to appear in --changed-only output.\n"
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
        """Second deploy with --changed-only --archive-orphans must not archive anything.

        Reproduces issue #3: run --changed-only --archive-orphans when no files
        have changed since the previous deploy. All pages must remain deployed.
        """
        # Step 1: clean deploy — ensures both pages exist in Confluence and state
        result = ccfm_run("--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        data_before = json.loads(SMOKE_STATE.read_text())
        pages_before = set(data_before["pages"].keys())
        assert pages_before, "State is empty after initial deploy"

        # Step 2: re-run with both flags — no files have changed, must be a no-op
        result = ccfm_run(
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

        # All pages tracked before must still be in state
        data_after = json.loads(SMOKE_STATE.read_text())
        pages_after = set(data_after["pages"].keys())
        archived = pages_before - pages_after
        assert not archived, (
            f"Pages were incorrectly archived during a no-op run: {archived}\n"
            f"stdout: {result.stdout}"
        )

    def test_unchanged_files_not_treated_as_orphans(self, ccfm_run, confluence_live):
        """When only one file changes, unchanged files on disk must not be archived.

        Reproduces issue #3 (Bug 2): orphan detection must use all current disk
        files, not just the --changed-only subset.
        """
        # Step 1: clean baseline deploy
        result = ccfm_run("--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        data_before = json.loads(SMOKE_STATE.read_text())
        beta_entries = [k for k in data_before["pages"] if BETA_KEY in k]
        assert beta_entries, "page-beta not in state after deploy"

        # Step 2: modify page-alpha only → --changed-only will deploy it, but
        # page-beta is unchanged on disk and must not be treated as an orphan
        original_content = PAGE_ALPHA.read_text(encoding="utf-8")
        modified_content = original_content.replace(
            "Version: **1**",
            "Version: **3** — orphan regression test",
        )
        try:
            PAGE_ALPHA.write_text(modified_content, encoding="utf-8")

            result = ccfm_run(
                "--changed-only",
                "--archive-orphans",
                "--directory",
                str(STATE_DIR),
                check=False,
            )

            assert (
                result.returncode == 0
            ), f"--changed-only --archive-orphans failed:\n{result.stderr}"

            # page-beta must still be in state — it's on disk, not an orphan
            data_after = json.loads(SMOKE_STATE.read_text())
            beta_still_present = [k for k in data_after["pages"] if BETA_KEY in k]
            assert beta_still_present, (
                f"page-beta was incorrectly archived as an orphan.\n"
                f"State after: {list(data_after['pages'].keys())}\n"
                f"stdout: {result.stdout}"
            )
        finally:
            PAGE_ALPHA.write_text(original_content, encoding="utf-8")


class TestArchiveOrphans:
    """--archive-orphans removes pages no longer tracked in the directory."""

    def test_archive_orphans_removes_absent_page(self, ccfm_run, confluence_live):
        """Deploy alpha+beta, then run with --archive-orphans on alpha-only dir.

        The beta page should be archived and removed from state.
        """
        # Step 1: Deploy both pages to ensure beta is tracked
        result = ccfm_run("--directory", str(STATE_DIR))
        assert result.returncode == 0, f"Initial deploy failed:\n{result.stderr}"

        data = json.loads(SMOKE_STATE.read_text())
        beta_entries = [k for k in data["pages"] if BETA_KEY in k]
        assert (
            beta_entries
        ), f"page-beta.md not in state before archive test. State: {list(data['pages'].keys())}"

        beta_page_id = data["pages"][beta_entries[0]]["page_id"]
        assert beta_page_id, "page-beta page_id is empty"

        # Step 2: Temporarily move page-beta out of the directory so it becomes an orphan
        beta_backup = PAGE_BETA.with_suffix(".md.bak")
        PAGE_BETA.rename(beta_backup)

        try:
            result = ccfm_run(
                "--archive-orphans",
                "--directory",
                str(STATE_DIR),
                "--docs-root",
                str(STATE_DIR),
            )

            assert result.returncode == 0, f"--archive-orphans failed:\n{result.stderr}"

            # beta should be archived and its state entry removed (or marked archived)
            data_after = json.loads(SMOKE_STATE.read_text())
            pages_after = data_after.get("pages", {})

            beta_still_active = [
                k
                for k, v in pages_after.items()
                if BETA_KEY in k and v.get("page_id") == beta_page_id
            ]
            assert not beta_still_active, (
                f"page-beta is still active in state after --archive-orphans.\n"
                f"State: {pages_after}"
            )

        finally:
            # Restore page-beta so subsequent tests/cleanup can find it
            beta_backup.rename(PAGE_BETA)
