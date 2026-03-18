"""Smoke tests: domain normalization strips protocol prefix before API calls."""

import subprocess
import sys

import pytest

from tests.smoke.conftest import PROJECT_ROOT, SMOKE_DOCS

pytestmark = pytest.mark.smoke

CONFIG_PAGE = SMOKE_DOCS / "single-page" / "single-page.md"


class TestDomainNormalization:
    """Verify that https:// prefixed domains are normalized before API calls."""

    def test_plan_with_https_prefixed_domain(self, smoke_creds, confluence_live):
        """plan succeeds when domain is provided with https:// prefix."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--domain",
                f"https://{smoke_creds['domain']}",
                "--email",
                smoke_creds["email"],
                "--token",
                smoke_creds["token"],
                "--space",
                smoke_creds["space"],
                "plan",
                "--file",
                str(CONFIG_PAGE),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert (
            result.returncode == 0
        ), f"plan with https:// domain failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_plan_with_domain_and_path(self, smoke_creds, confluence_live):
        """plan succeeds when domain includes a /wiki path component."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ccfm_convert",
                "--domain",
                f"https://{smoke_creds['domain']}/wiki",
                "--email",
                smoke_creds["email"],
                "--token",
                smoke_creds["token"],
                "--space",
                smoke_creds["space"],
                "plan",
                "--file",
                str(CONFIG_PAGE),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert (
            result.returncode == 0
        ), f"plan with domain/wiki path failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
