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
    """Apply acquires/releases lock automatically; lock commands work."""

    def test_lock_status_shows_unlocked(self, ccfm_run, confluence_live):
        """ccfm lock status shows unlocked when no apply is running."""
        result = ccfm_run("lock", "status")

        assert result.returncode == 0, f"Lock status failed:\n{result.stderr}"
        assert (
            "unlocked" in result.stdout.lower() or "not locked" in result.stdout.lower()
        ), f"Expected unlocked status.\nstdout: {result.stdout}"

    def test_apply_acquires_and_releases_lock(self, ccfm_run, confluence_live):
        """After an apply completes, the lock is released."""
        # Apply a page
        result = ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))
        assert result.returncode == 0, f"Apply failed:\n{result.stderr}"

        # Lock should be released after apply
        result = ccfm_run("lock", "status")
        assert result.returncode == 0
        assert (
            "unlocked" in result.stdout.lower() or "not locked" in result.stdout.lower()
        ), f"Lock should be released after apply.\nstdout: {result.stdout}"

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
    """ccfm state list, show, pull, push, and rm commands."""

    def test_state_list_shows_deployed_pages(self, ccfm_run, confluence_live):
        """ccfm state list shows pages after an apply."""
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        result = ccfm_run("state", "list")

        assert result.returncode == 0, f"State list failed:\n{result.stderr}"
        assert (
            "single-page" in result.stdout
        ), f"Expected single-page in state list.\nstdout: {result.stdout}"

    def test_state_pull_outputs_json(self, ccfm_run, confluence_live):
        """ccfm state pull outputs valid JSON to stdout."""
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        result = ccfm_run("state", "pull")
        assert result.returncode == 0, f"State pull failed:\n{result.stderr}"

        import json

        state = json.loads(result.stdout)
        assert "pages" in state, "State JSON missing 'pages' key"
        assert "version" in state, "State JSON missing 'version' key"

    def test_state_show_displays_entry(self, ccfm_run, confluence_live):
        """ccfm state show <path> outputs the entry for a specific page."""
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        # Find the .md state key
        list_result = ccfm_run("state", "list")
        state_key = None
        for line in list_result.stdout.strip().split("\n"):
            stripped = line.strip()
            if stripped.endswith("single-page.md"):
                state_key = stripped.split()[0] if stripped else None
                break

        assert state_key, f"Could not find single-page.md in state list:\n{list_result.stdout}"

        result = ccfm_run("state", "show", state_key)
        assert result.returncode == 0, f"State show failed:\n{result.stderr}"
        assert "page_id" in result.stdout, "State show output missing page_id"

    def test_state_push_round_trip(self, ccfm_run, confluence_live, tmp_path):
        """state pull -> push round-trip preserves state."""
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        # Pull current state
        pull_result = ccfm_run("state", "pull")
        assert pull_result.returncode == 0

        # Write to a temp file and push it back
        state_file = tmp_path / "state.json"
        state_file.write_text(pull_result.stdout)

        push_result = ccfm_run("state", "push", str(state_file))
        assert push_result.returncode == 0, f"State push failed:\n{push_result.stderr}"
        assert (
            "updated" in push_result.stdout.lower()
        ), f"Expected 'updated' in push output:\n{push_result.stdout}"

        # Verify state is still intact
        verify_result = ccfm_run("state", "list")
        assert "single-page" in verify_result.stdout

    def test_state_rm_removes_entry(self, ccfm_run, confluence_live):
        """ccfm state rm removes a page entry from remote state."""
        ccfm_run("apply", "--auto-approve", "--file", str(SINGLE_PAGE))

        # Find the state key by listing
        list_result = ccfm_run("state", "list")
        # Extract a path that contains single-page
        lines = list_result.stdout.strip().split("\n")
        state_key = None
        for line in lines:
            if "single-page.md" in line:
                # The state key is typically the first column or the path
                state_key = line.strip().split()[0] if line.strip() else None
                break

        assert state_key, f"Could not find single-page key in state list:\n{list_result.stdout}"

        result = ccfm_run("state", "rm", state_key)
        assert result.returncode == 0, f"State rm failed:\n{result.stderr}"
        assert (
            f"Removed '{state_key}' from state." in result.stdout
        ), f"Expected removal confirmation for {state_key}.\nstdout: {result.stdout}"

        # Verify the exact .md path is removed from state
        list_after = ccfm_run("state", "list")
        listed_paths = [
            ln.strip().split()[0]
            for ln in list_after.stdout.strip().split("\n")
            if ln.strip() and ln.strip()[0] != " " and not ln.strip().startswith("Tracked")
        ]
        assert (
            state_key not in listed_paths
        ), f"State key {state_key} still present after rm.\nstdout: {list_after.stdout}"


class TestLockAcquireAndBlock:
    """Lock acquire blocks apply, lock release unblocks."""

    def test_lock_acquire_blocks_apply(self, ccfm_run, confluence_live):
        """Manually acquired lock blocks a subsequent apply."""
        # Acquire lock manually
        acquire_result = ccfm_run("lock", "acquire")
        assert acquire_result.returncode == 0, f"Lock acquire failed:\n{acquire_result.stderr}"

        try:
            # Apply should fail because lock is held
            apply_result = ccfm_run(
                "apply", "--auto-approve", "--force", "--file", str(SINGLE_PAGE), check=False
            )
            assert apply_result.returncode != 0, "Apply should fail when lock is held"
            assert (
                "locked" in apply_result.stdout.lower() or "locked" in apply_result.stderr.lower()
            )
        finally:
            # Always release lock to avoid blocking other tests
            ccfm_run("lock", "release", check=False)
