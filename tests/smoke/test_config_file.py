"""Smoke tests: deployment via --config ccfm.yaml with ${ENV_VAR} interpolation."""

import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT, SMOKE_DIR, SMOKE_DOCS

pytestmark = pytest.mark.smoke

CONFIG_FILE = SMOKE_DIR / "ccfm-smoke.yaml"
CONFIG_PAGE = SMOKE_DOCS / "config-test" / "config-page.md"


class TestConfigFileDeploy:
    """Deploy using a ccfm.yaml config file instead of inline CLI flags."""

    def test_apply_via_config_file(self, confluence_live):
        """--config ccfm.yaml with ${ENV_VAR} interpolation deploys successfully."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(CONFIG_FILE),
                "apply",
                "--auto-approve",
                "--file",
                str(CONFIG_PAGE),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Config-file apply failed:\n{result.stderr}"
        assert (
            "Success" in result.stdout or "Updating" in result.stdout or "Creating" in result.stdout
        ), f"Unexpected output:\n{result.stdout}"
