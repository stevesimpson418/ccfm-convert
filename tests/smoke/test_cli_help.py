"""Smoke tests: CLI help outputs for all subcommands.

These tests are lightweight — no credentials or Confluence access needed.
They verify that --help exits 0 and produces sensible output for every subcommand.
"""

import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT

pytestmark = pytest.mark.smoke


def _run_help(*args):
    """Run ccfm with --help and return the CompletedProcess."""
    cmd = [sys.executable, "-m", "ccfm_convert", *args, "--help"]
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TestHelpOutputs:
    """Validate --help for each subcommand exits 0."""

    def test_root_help(self):
        result = _run_help()
        assert result.returncode == 0
        assert "Deploy markdown to Confluence" in result.stdout

    def test_init_help(self):
        result = _run_help("init")
        assert result.returncode == 0

    def test_plan_help(self):
        result = _run_help("plan")
        assert result.returncode == 0
        assert "--docs-root" in result.stdout
        assert "--debug-file" in result.stdout

    def test_apply_help(self):
        result = _run_help("apply")
        assert result.returncode == 0
        assert "--auto-approve" in result.stdout
        assert "--docs-root" in result.stdout

    def test_state_help(self):
        result = _run_help("state")
        assert result.returncode == 0
        assert "list" in result.stdout
        assert "pull" in result.stdout

    def test_lock_help(self):
        result = _run_help("lock")
        assert result.returncode == 0
        assert "status" in result.stdout
        assert "release" in result.stdout
