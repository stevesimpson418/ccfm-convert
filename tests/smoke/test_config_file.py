"""Smoke tests: deployment via --config ccfm.yaml with ${ENV_VAR} interpolation."""

import json

import pytest

from tests.smoke.conftest import SMOKE_DIR, SMOKE_DOCS, SMOKE_STATE

pytestmark = pytest.mark.smoke

CONFIG_FILE = SMOKE_DIR / "ccfm-smoke.yaml"
CONFIG_PAGE = SMOKE_DOCS / "config-test" / "config-page.md"


class TestConfigFileDeploy:
    """Deploy using a ccfm.yaml config file instead of inline CLI flags."""

    def test_deploy_via_config_file(self, smoke_state):
        """--config ccfm.yaml with ${ENV_VAR} interpolation deploys successfully."""
        import subprocess
        import sys

        from tests.smoke.conftest import PROJECT_ROOT

        result = subprocess.run(
            [
                sys.executable,
                "src/main.py",
                "--config",
                str(CONFIG_FILE),
                "--file",
                str(CONFIG_PAGE),
                "--state",
                str(SMOKE_STATE),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Config-file deploy failed:\n{result.stderr}"
        assert (
            "Success" in result.stdout or "Updating" in result.stdout or "Creating" in result.stdout
        ), f"Unexpected output:\n{result.stdout}"

        assert smoke_state.exists(), "State file was not created after config-file deploy"
        data = json.loads(smoke_state.read_text())
        pages = data.get("pages", {})

        matching = [v for k, v in pages.items() if "config-page.md" in k]
        assert matching, f"config-page.md not found in state. State: {list(pages.keys())}"
        assert matching[0]["page_id"], "page_id is empty for config-page"
