"""Smoke tests: global ci_banner toggle from ccfm.yaml config."""

import json
import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT

pytestmark = pytest.mark.smoke


class TestGlobalCIBanner:
    """Verify ci_banner toggle in ccfm.yaml flows through to ADF output."""

    def test_global_ci_banner_false_disables_banner(self, tmp_path):
        """plan --debug-file omits the banner when ccfm.yaml sets ci_banner: false."""
        config = tmp_path / "ccfm.yaml"
        config.write_text("ci_banner: false\n")

        test_file = tmp_path / "test.md"
        test_file.write_text("# Simple page\n\nSome content.")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(config),
                "plan",
                "--debug-file",
                str(test_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"debug-file failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        # No banner panel should be prepended.
        assert data["content"][0]["type"] != "panel"

    def test_frontmatter_overrides_global_ci_banner_false(self, tmp_path):
        """Per-page ci_banner: true overrides global ci_banner: false."""
        config = tmp_path / "ccfm.yaml"
        config.write_text("ci_banner: false\n")

        test_file = tmp_path / "test.md"
        test_file.write_text("---\ndeploy_config:\n  ci_banner: true\n---\n# Test")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(config),
                "plan",
                "--debug-file",
                str(test_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"debug-file failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        assert data["content"][0]["type"] == "panel"

    def test_no_ci_banner_cli_flag_disables_banner(self, tmp_path):
        """--no-ci-banner CLI flag disables the banner."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Simple page\n\nSome content.")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "plan",
                "--no-ci-banner",
                "--debug-file",
                str(test_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"debug-file failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        assert data["content"][0]["type"] != "panel"

    def test_default_banner_when_no_global_or_frontmatter(self, tmp_path):
        """Banner is shown by default when neither config nor frontmatter set ci_banner."""
        config = tmp_path / "ccfm.yaml"
        config.write_text("version: 1\n")

        test_file = tmp_path / "test.md"
        test_file.write_text("# Simple page\n\nSome content.")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(config),
                "plan",
                "--debug-file",
                str(test_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"debug-file failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        assert data["content"][0]["type"] == "panel"
