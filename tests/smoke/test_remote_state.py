"""Smoke tests: remote state initialisation, locking, and state commands."""

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

SINGLE_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"


class TestInit:
    """ccfm init creates the _ccfm management infrastructure."""

    def test_init_creates_management_page(self, ccfm_run, confluence_live):
        """ccfm init creates _ccfm container and management page."""
        result = ccfm_run("init")

        assert result.returncode == 0, f"Init failed:\n{result.stderr}"
        assert (
            "Initialised" in result.stdout
            or "already initialised" in result.stdout
            or "Management page" in result.stdout
        ), f"Unexpected init output:\n{result.stdout}"

    def test_init_is_idempotent(self, ccfm_run, confluence_live):
        """Running ccfm init again is a no-op."""
        # First init
        ccfm_run("init")

        # Second init should succeed without error
        result = ccfm_run("init")
        assert result.returncode == 0, f"Idempotent init failed:\n{result.stderr}"


class TestLocking:
    """Deploy acquires/releases lock automatically; lock commands work."""

    def test_lock_status_shows_unlocked(self, ccfm_run, confluence_live):
        """ccfm lock status shows unlocked when no deploy is running."""
        result = ccfm_run("lock", "status")

        assert result.returncode == 0, f"Lock status failed:\n{result.stderr}"
        assert (
            "unlocked" in result.stdout.lower() or "not locked" in result.stdout.lower()
        ), f"Expected unlocked status.\nstdout: {result.stdout}"

    def test_deploy_acquires_and_releases_lock(self, ccfm_run, confluence_live):
        """After a deploy completes, the lock is released."""
        # Deploy a page
        result = ccfm_run("deploy", "--file", str(SINGLE_PAGE))
        assert result.returncode == 0, f"Deploy failed:\n{result.stderr}"

        # Lock should be released after deploy
        result = ccfm_run("lock", "status")
        assert result.returncode == 0
        assert (
            "unlocked" in result.stdout.lower() or "not locked" in result.stdout.lower()
        ), f"Lock should be released after deploy.\nstdout: {result.stdout}"

    def test_force_release_is_idempotent(self, ccfm_run, confluence_live):
        """lock release succeeds whether locked or unlocked (idempotent).

        Uses check=False so we capture the returncode and get a meaningful
        assertion error if it fails, rather than an unhandled CalledProcessError.
        Calls release twice: once to clear any state, once to confirm idempotency.
        """
        # First call — may or may not have an existing lock, should always succeed
        result = ccfm_run("lock", "release", check=False)
        assert result.returncode == 0, f"First lock release failed:\n{result.stderr}"

        # Second call — lock is definitely gone now; must still exit 0 (idempotent)
        result = ccfm_run("lock", "release", check=False)
        assert result.returncode == 0, f"Second lock release failed (idempotency):\n{result.stderr}"


class TestStateCommands:
    """ccfm state list and ccfm state rm commands."""

    def test_state_list_shows_deployed_pages(self, ccfm_run, confluence_live):
        """ccfm state list shows pages after a deploy."""
        ccfm_run("deploy", "--file", str(SINGLE_PAGE))

        result = ccfm_run("state", "list")

        assert result.returncode == 0, f"State list failed:\n{result.stderr}"
        assert (
            "single-page" in result.stdout
        ), f"Expected single-page in state list.\nstdout: {result.stdout}"

    def test_state_rm_removes_entry(self, ccfm_run, confluence_live):
        """ccfm state rm removes a page entry from remote state."""
        ccfm_run("deploy", "--file", str(SINGLE_PAGE))

        # Find the state key by listing
        list_result = ccfm_run("state", "list")
        # Extract a path that contains single-page
        lines = list_result.stdout.strip().split("\n")
        state_key = None
        for line in lines:
            if "single-page" in line:
                # The state key is typically the first column or the path
                state_key = line.strip().split()[0] if line.strip() else None
                break

        if state_key:
            result = ccfm_run("state", "rm", state_key)
            assert result.returncode == 0, f"State rm failed:\n{result.stderr}"

            # Verify it's removed
            list_after = ccfm_run("state", "list")
            assert state_key not in list_after.stdout, (
                f"State key {state_key} still present after rm.\n" f"stdout: {list_after.stdout}"
            )
