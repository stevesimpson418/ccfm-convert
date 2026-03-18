"""Smoke tests: docs_root from ccfm.yaml used as fallback for --directory."""

import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT, SMOKE_DIR

pytestmark = pytest.mark.smoke

CONFIG_FILE = SMOKE_DIR / "ccfm-docs-root-smoke.yaml"


class TestDocsRootFallback:
    """Verify that plan and apply work without --directory when docs_root is in config."""

    def test_plan_without_directory_uses_docs_root(self, confluence_live):
        """plan succeeds without --file or --directory when config has docs_root."""
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
        ), f"plan without --directory failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        # Should show plan output (either "No changes" or a list of add/change actions)
        assert (
            "No changes" in result.stdout
            or "to add" in result.stdout
            or "to change" in result.stdout
        ), f"Unexpected plan output:\n{result.stdout}"

    def test_apply_without_directory_uses_docs_root(self, confluence_live):
        """apply --auto-approve succeeds without --directory when config has docs_root."""
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
        ), f"apply without --directory failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert (
            "Apply complete" in result.stdout or "No changes" in result.stdout
        ), f"Unexpected apply output:\n{result.stdout}"
