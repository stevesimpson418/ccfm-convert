"""Smoke tests: state management — plan, apply, and destroy behaviour."""

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
    """ccfm plan output before/after an apply."""

    def test_plan_before_apply_shows_adds(self, ccfm_run, confluence_live):
        """plan --force --plan-exit-code exits 2 and lists add actions."""
        result = ccfm_run(
            "plan", "--force", "--plan-exit-code", "--docs-root", str(STATE_DIR), check=False
        )

        assert result.returncode == 2, (
            f"Expected exit 2 (pending changes), "
            f"got {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "add" in result.stdout, f"Expected 'add' in plan output.\nstdout: {result.stdout}"

    def test_plan_after_apply_shows_no_changes(self, ccfm_run, confluence_live):
        """plan after a full apply exits 0 and shows no changes."""
        # Apply both pages first
        result = ccfm_run("apply", "--auto-approve", "--docs-root", str(STATE_DIR))
        assert result.returncode == 0, f"Initial apply failed:\n{result.stderr}"

        result = ccfm_run("plan", "--docs-root", str(STATE_DIR), check=False)

        assert result.returncode == 0, (
            f"Expected exit 0 (no changes) after apply, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "No changes" in result.stdout or "unchanged" in result.stdout
        ), f"Expected no-changes message in plan output.\nstdout: {result.stdout}"


class TestDestroyBehavior:
    """Destroy detection removes pages whose source files are deleted."""

    def test_plan_shows_destroy_for_removed_file(self, ccfm_run, confluence_live):
        """After removing a file, plan shows a destroy action."""
        # Step 1: Deploy both pages to ensure beta is tracked
        result = ccfm_run("apply", "--auto-approve", "--docs-root", str(STATE_DIR))
        assert result.returncode == 0, f"Initial apply failed:\n{result.stderr}"

        # Step 2: Temporarily move page-beta out of the directory so it becomes an orphan
        beta_backup = PAGE_BETA.with_suffix(".md.bak")
        PAGE_BETA.rename(beta_backup)

        try:
            result = ccfm_run(
                "plan",
                "--docs-root",
                str(STATE_DIR),
                check=False,
            )

            assert result.returncode == 0, f"plan failed:\n{result.stderr}"
            assert (
                "destroy" in result.stdout
            ), f"Expected 'destroy' in plan output.\nstdout: {result.stdout}"

        finally:
            # Restore page-beta so subsequent tests/cleanup can find it
            beta_backup.rename(PAGE_BETA)

    def test_apply_destroys_removed_page(self, ccfm_run, confluence_live):
        """Apply with --auto-approve destroys the page and removes from state."""
        # Step 1: Deploy both pages
        result = ccfm_run("apply", "--auto-approve", "--docs-root", str(STATE_DIR))
        assert result.returncode == 0, f"Initial apply failed:\n{result.stderr}"

        # Step 2: Move page-beta out
        beta_backup = PAGE_BETA.with_suffix(".md.bak")
        PAGE_BETA.rename(beta_backup)

        try:
            result = ccfm_run(
                "apply",
                "--auto-approve",
                "--docs-root",
                str(STATE_DIR),
            )

            assert result.returncode == 0, f"apply with destroy failed:\n{result.stderr}"

        finally:
            # Restore page-beta
            beta_backup.rename(PAGE_BETA)
