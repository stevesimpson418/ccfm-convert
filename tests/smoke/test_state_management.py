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
        """--plan before any deploy exits 2 and lists CREATE actions."""
        # Ensure no pre-existing state for this directory
        SMOKE_STATE.unlink(missing_ok=True)

        result = ccfm_run("--plan", "--directory", str(STATE_DIR), check=False)

        assert result.returncode == 2, (
            f"Expected exit 2 (pending changes) before first deploy, "
            f"got {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "CREATE" in result.stdout
        ), f"Expected 'CREATE' in --plan output before deploy.\nstdout: {result.stdout}"

    def test_plan_after_deploy_shows_no_ops(self, ccfm_run):
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

    def test_changed_only_skips_unchanged(self, ccfm_run):
        """After a clean deploy, --changed-only reports 0 files with changes."""
        # Ensure both pages are deployed (may already be from TestPlanMode)
        ccfm_run("--directory", str(STATE_DIR))

        result = ccfm_run("--changed-only", "--directory", str(STATE_DIR))

        assert result.returncode == 0, f"--changed-only failed:\n{result.stderr}"
        assert (
            "0 file(s) with changes" in result.stdout
        ), f"Expected '0 file(s) with changes' in output.\nstdout: {result.stdout}"

    def test_changed_only_deploys_modified_file(self, ccfm_run, tmp_path):
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


class TestArchiveOrphans:
    """--archive-orphans removes pages no longer tracked in the directory."""

    def test_archive_orphans_removes_absent_page(self, ccfm_run):
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
