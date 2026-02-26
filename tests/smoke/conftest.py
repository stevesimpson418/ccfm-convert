"""Smoke test infrastructure: credentials, cleanup, and shared fixtures.

Usage
-----
Run all smoke tests and auto-cleanup Confluence pages when done:

    pytest tests/smoke/ --no-cov -v

Leave pages in Confluence for manual inspection (no cleanup):

    pytest tests/smoke/ --no-cov -v --no-cleanup

Delete pages from a previous --no-cleanup run without re-running tests:

    pytest tests/smoke/ --no-cov -v --cleanup-only

Environment variables required
-------------------------------
    CONFLUENCE_DOMAIN   e.g. ccfm.atlassian.net
    CONFLUENCE_EMAIL    e.g. user@example.com
    CONFLUENCE_TOKEN    Atlassian API token

Or: copy .env.smoke.example to .env, fill in values, then ``source .env``.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SMOKE_DIR = Path(__file__).parent
SMOKE_STATE = SMOKE_DIR / ".ccfm-smoke-state.json"
SMOKE_DOCS = SMOKE_DIR / "docs"
PROJECT_ROOT = SMOKE_DIR.parent.parent

# Space used for all smoke tests (read-only — change via CCFM_SMOKE_SPACE env var)
SMOKE_SPACE = os.environ.get("CCFM_SMOKE_SPACE", "CCFMDEV")


# ---------------------------------------------------------------------------
# Custom CLI options
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--no-cleanup",
        action="store_true",
        default=False,
        help="Skip Confluence page cleanup after smoke tests (leave pages for manual inspection)",
    )
    parser.addoption(
        "--cleanup-only",
        action="store_true",
        default=False,
        help=(
            "Delete all pages from a previous smoke run without re-running tests. "
            "Reads from the existing smoke state file."
        ),
    )


def pytest_collection_modifyitems(config, items):
    """Skip all tests when --cleanup-only is set — only cleanup will run."""
    if config.getoption("--cleanup-only"):
        skip = pytest.mark.skip(
            reason="--cleanup-only: skipping deploy tests, running cleanup only"
        )
        for item in items:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Session cleanup hook — runs after all tests regardless of results
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session, exitstatus):
    """Delete all Confluence pages tracked in the smoke state file."""
    try:
        no_cleanup = session.config.getoption("--no-cleanup", default=False)
    except ValueError:
        no_cleanup = False

    if no_cleanup:
        print(
            f"\n\nSmoke state preserved at: {SMOKE_STATE}"
            "\nRun with --cleanup-only to delete pages later."
        )
        return

    _delete_smoke_pages()


def _delete_smoke_pages():
    """Permanently delete all Confluence pages tracked in the smoke state file."""
    if not SMOKE_STATE.exists():
        return

    try:
        data = json.loads(SMOKE_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    domain = os.environ.get("CONFLUENCE_DOMAIN", "")
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("CONFLUENCE_TOKEN", "")

    if not (domain and email and token):
        print("\nWarning: credentials not available for smoke cleanup — state file left in place.")
        return

    auth = (email, token)
    pages = data.get("pages", {})
    deleted = 0
    failed = 0

    print(f"\n\nCleaning up {len(pages)} smoke test page(s)...")
    for rel_path, entry in pages.items():
        page_id = entry.get("page_id")
        title = entry.get("title", rel_path)
        if not page_id:
            continue
        url = f"https://{domain}/wiki/api/v2/pages/{page_id}"
        try:
            resp = requests.delete(url, auth=auth, timeout=15)
            if resp.status_code in (200, 204, 404):
                print(f"  ✓ Deleted: {title} (ID: {page_id})")
                deleted += 1
            else:
                print(f"  ✗ Failed to delete: {title} ({resp.status_code})")
                failed += 1
        except requests.RequestException as e:
            print(f"  ✗ Error deleting {title}: {e}")
            failed += 1

    SMOKE_STATE.unlink(missing_ok=True)
    print(f"Cleanup complete: {deleted} deleted, {failed} failed.")


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def smoke_creds():
    """Return Confluence credentials from environment variables.

    Skips the entire test session if any required variable is missing.
    """
    required = {
        "domain": "CONFLUENCE_DOMAIN",
        "email": "CONFLUENCE_EMAIL",
        "token": "CONFLUENCE_TOKEN",
    }
    creds = {}
    missing = []
    for key, env_var in required.items():
        val = os.environ.get(env_var)
        if not val:
            missing.append(env_var)
        creds[key] = val or ""

    if missing:
        pytest.skip(
            f"Smoke test credentials not set: {', '.join(missing)}. "
            "See .env.smoke.example for setup instructions."
        )

    creds["space"] = SMOKE_SPACE
    return creds


@pytest.fixture(scope="session")
def ccfm_run(smoke_creds):
    """Return a callable that invokes src/main.py with smoke credentials.

    All invocations share the same state file (``SMOKE_STATE``) so page IDs
    are preserved across test functions within the session.

    Args:
        *extra_args: Additional CLI arguments passed after the base credential flags.
        check (bool): If True (default), raise CalledProcessError on non-zero exit.

    Returns:
        subprocess.CompletedProcess
    """

    def _run(*extra_args, check=True):
        cmd = [
            sys.executable,
            "src/main.py",
            "--domain",
            smoke_creds["domain"],
            "--email",
            smoke_creds["email"],
            "--token",
            smoke_creds["token"],
            "--space",
            smoke_creds["space"],
            "--state",
            str(SMOKE_STATE),
            *extra_args,
        ]
        return subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=check,
        )

    return _run


@pytest.fixture(scope="session")
def smoke_state():
    """Return the path to the shared smoke state file."""
    return SMOKE_STATE


@pytest.fixture(scope="session")
def smoke_docs():
    """Return the root path of the smoke test fixture docs."""
    return SMOKE_DOCS
