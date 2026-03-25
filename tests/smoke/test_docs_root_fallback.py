"""Smoke tests: docs_root from ccfm.yaml config."""

import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT, SMOKE_DIR

pytestmark = pytest.mark.smoke

CONFIG_FILE = SMOKE_DIR / "ccfm-docs-root-smoke.yaml"


class TestDocsRootFromConfig:
    """Verify that plan and apply work using docs_root from ccfm.yaml config."""

    def test_plan_uses_docs_root_from_config(self, confluence_live):
        """plan succeeds using docs_root from config file."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(CONFIG_FILE),
                "plan",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert (
            result.returncode == 0
        ), f"plan with docs_root config failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert (
            "No changes" in result.stdout
            or "to add" in result.stdout
            or "to change" in result.stdout
        ), f"Unexpected plan output:\n{result.stdout}"

    def test_apply_uses_docs_root_from_config(self, confluence_live):
        """apply --auto-approve succeeds using docs_root from config file."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(CONFIG_FILE),
                "apply",
                "--auto-approve",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert (
            result.returncode == 0
        ), f"apply with docs_root config failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert (
            "Apply complete" in result.stdout or "No changes" in result.stdout
        ), f"Unexpected apply output:\n{result.stdout}"
