"""Smoke tests: single-file deployment via --file."""

import json

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

SINGLE_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"


class TestSingleFileDeploy:
    """Deploy a single markdown file and verify state tracking."""

    def test_page_created(self, ccfm_run, smoke_state):
        """--file deploys successfully and state file records the page_id."""
        result = ccfm_run("--file", str(SINGLE_PAGE))

        assert result.returncode == 0, f"Deploy failed:\n{result.stderr}"
        assert (
            "Success" in result.stdout or "Updating" in result.stdout or "Creating" in result.stdout
        )

        assert smoke_state.exists(), "State file was not created after deploy"
        data = json.loads(smoke_state.read_text())
        pages = data.get("pages", {})

        # State key is relative to project root
        matching = [v for k, v in pages.items() if "single-page.md" in k]
        assert matching, f"single-page.md not found in state. State: {list(pages.keys())}"
        assert matching[0]["page_id"], "page_id is empty in state"

    def test_page_updated_on_redeploy(self, ccfm_run, smoke_state):
        """Re-deploying the same file updates (not duplicates) the page — same page_id."""
        assert smoke_state.exists(), "State must exist from test_page_created"
        data_before = json.loads(smoke_state.read_text())
        page_id_before = next(
            v["page_id"] for k, v in data_before["pages"].items() if "single-page.md" in k
        )

        result = ccfm_run("--file", str(SINGLE_PAGE))
        assert result.returncode == 0

        data_after = json.loads(smoke_state.read_text())
        page_id_after = next(
            v["page_id"] for k, v in data_after["pages"].items() if "single-page.md" in k
        )

        assert page_id_before == page_id_after, (
            f"page_id changed between deploys: {page_id_before} → {page_id_after}. "
            "This indicates a duplicate page was created instead of updated."
        )
        assert "Updating" in result.stdout, "Expected 'Updating' in output for a re-deploy"

    def test_dump_mode_writes_adf_no_state_change(self, ccfm_run, smoke_state):
        """--dump writes an .adf.json file locally and does not modify the state file."""
        adf_file = SINGLE_PAGE.with_suffix(".adf.json")
        adf_file.unlink(missing_ok=True)

        state_before = smoke_state.read_text() if smoke_state.exists() else None

        result = ccfm_run("--file", str(SINGLE_PAGE), "--dump")
        assert result.returncode == 0
        assert adf_file.exists(), ".adf.json file was not written by --dump"

        state_after = smoke_state.read_text() if smoke_state.exists() else None
        assert (
            state_before == state_after
        ), "State file was modified during --dump (it should not be)"

        # Cleanup the generated file
        adf_file.unlink(missing_ok=True)
