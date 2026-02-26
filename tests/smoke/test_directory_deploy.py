"""Smoke tests: directory deployment via --directory."""

import json

import pytest

from tests.smoke.conftest import SMOKE_DOCS

pytestmark = pytest.mark.smoke

EXAMPLE_DIR = SMOKE_DOCS / "example"

# The three markdown files inside the example tree
EXAMPLE_MD_FILES = [
    "CCFM Example/complete_example.md",
    "CCFM Example/My App/my_app.md",
    "CCFM Example/My Team/my_team.md",
]


class TestDirectoryDeploy:
    """Deploy an entire directory tree and verify all pages appear in state."""

    def test_tree_creates_all_pages(self, ccfm_run, smoke_state):
        """--directory deploys all markdown files; state tracks each page_id."""
        result = ccfm_run("--directory", str(EXAMPLE_DIR))

        assert result.returncode == 0, f"Directory deploy failed:\n{result.stderr}"
        assert smoke_state.exists(), "State file was not created after directory deploy"

        data = json.loads(smoke_state.read_text())
        pages = data.get("pages", {})

        for rel in EXAMPLE_MD_FILES:
            # State keys contain the path relative to project root
            matching = [v for k, v in pages.items() if rel in k]
            assert matching, f"{rel} not found in state. State keys: {list(pages.keys())}"
            assert matching[0]["page_id"], f"page_id is empty for {rel}"

    def test_plan_shows_no_ops_after_deploy(self, ccfm_run, smoke_state):
        """--plan after a full deploy reports NO-OP for all pages and exits 0."""
        assert smoke_state.exists(), "State must exist from test_tree_creates_all_pages"

        result = ccfm_run("--plan", "--directory", str(EXAMPLE_DIR), check=False)

        assert result.returncode == 0, (
            f"--plan after deploy should exit 0 (all NO-OP), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "NO-OP" in result.stdout
        ), f"Expected 'NO-OP' in --plan output after deploy.\nstdout: {result.stdout}"
