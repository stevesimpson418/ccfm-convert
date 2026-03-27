"""Smoke tests: global ci_banner_text from ccfm.yaml config."""

import json
import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT, SMOKE_DOCS

pytestmark = pytest.mark.smoke

SINGLE_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"


class TestGlobalCIBannerText:
    """Verify ci_banner_text in ccfm.yaml flows through to ADF output."""

    def test_debug_file_uses_global_ci_banner_text(self, tmp_path):
        """plan --debug-file uses ci_banner_text from ccfm.yaml."""
        config = tmp_path / "ccfm.yaml"
        config.write_text('ci_banner_text: "Custom global banner from config"\n')

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(config),
                "plan",
                "--debug-file",
                str(SINGLE_PAGE),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"debug-file failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        banner_text = data["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == "Custom global banner from config"

    def test_frontmatter_overrides_global_ci_banner_text(self, tmp_path):
        """Per-page frontmatter ci_banner_text overrides global config value."""
        config = tmp_path / "ccfm.yaml"
        config.write_text('ci_banner_text: "Global banner"\n')

        test_file = tmp_path / "test.md"
        test_file.write_text(
            "---\ndeploy_config:\n  ci_banner_text: Page-level override\n---\n# Test"
        )

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
        banner_text = data["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == "Page-level override"

    def test_default_banner_when_no_config_or_frontmatter(self, tmp_path):
        """Default banner text used when neither config nor frontmatter set it."""
        config = tmp_path / "ccfm.yaml"
        config.write_text("version: 1\n")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--config",
                str(config),
                "plan",
                "--debug-file",
                str(SINGLE_PAGE),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"debug-file failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        banner_text = data["content"][0]["content"][0]["content"][0]["text"]
        assert "automatically generated" in banner_text
