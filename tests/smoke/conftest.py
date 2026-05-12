"""Smoke test infrastructure: credentials, cleanup, and shared fixtures.

Usage
-----
Run all smoke tests and auto-cleanup Confluence pages when done:

    pytest tests/smoke/ --no-cov -v

Leave pages in Confluence for manual inspection (no cleanup):

    pytest tests/smoke/ --no-cov -v --no-cleanup

Delete pages from a previous --no-cleanup run (skips re-running tests):

    pytest tests/smoke/ --no-cov -v --cleanup-only

Environment variables required
-------------------------------
    CONFLUENCE_DOMAIN   e.g. ccfm.atlassian.net
    CONFLUENCE_EMAIL    e.g. user@example.com
    CONFLUENCE_TOKEN    Atlassian API token

Or: copy .env.smoke.example to .env, fill in values, then ``source .env``.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import requests

# Mirror the backend's strict key shape (``ccfm-page-<sha256(path)[:16]>``) so
# teardown only touches properties the backend itself would have written. A
# loose ``startswith("ccfm-page-")`` would over-reach if some other tool ever
# wrote a property with that prefix and a non-conformant suffix.
_STATE_KEY_RE = re.compile(r"^ccfm-page-[0-9a-f]{16}$")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SMOKE_DIR = Path(__file__).parent
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
            "Cleans up the _ccfm management page and any deployed pages."
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
    """Delete deployed pages and the _ccfm management infrastructure."""
    try:
        no_cleanup = session.config.getoption("--no-cleanup", default=False)
    except ValueError:
        no_cleanup = False

    if no_cleanup:
        print("\n\nSmoke pages preserved in Confluence.")
        print("Run with --cleanup-only to delete pages later.")
        return

    _delete_smoke_pages()


def _delete_smoke_pages():
    """Delete deployed pages via remote state and reset state to empty.

    The _ccfm container and CCFM State Management page are preserved —
    they are one-time infrastructure and should not be torn down between runs.
    """
    domain = os.environ.get("CONFLUENCE_DOMAIN", "")
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("CONFLUENCE_TOKEN", "")

    if not (domain and email and token):
        print("\nWarning: credentials not available for smoke cleanup.")
        return

    auth = (email, token)
    space_key = SMOKE_SPACE

    # Step 1: Find space ID, container, and management page via container→child lookup.
    space_id = _get_space_id(domain, auth, space_key)
    if not space_id:
        print("\nWarning: could not look up space ID — skipping cleanup.")
        return

    container_id = _find_page_by_title_in_space(domain, auth, space_id, "_ccfm")
    if not container_id:
        print("\nNo _ccfm container found — nothing to clean up.")
        return

    mgmt_page_id = _find_child_by_title(domain, auth, container_id, "CCFM State Management")
    if not mgmt_page_id:
        print("\nNo CCFM State Management page found — skipping state cleanup.")
    else:
        # Step 2: Read remote state from per-page properties and delete tracked pages.
        state_pages = _load_state_pages(domain, auth, mgmt_page_id)
        if state_pages:
            deleted = 0
            failed = 0
            print(f"\n\nCleaning up {len(state_pages)} smoke test page(s)...")
            for rel_path, entry in state_pages.items():
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
            print(f"Pages cleanup: {deleted} deleted, {failed} failed.")

        # Step 3: Reset state to empty — preserves the management page for next run.
        _reset_state(domain, auth, mgmt_page_id)

    # Step 4: Delete hierarchy pages not tracked in state (created by ensure_page_hierarchy).
    # Must delete children before parent — Confluence v2 does not cascade-delete.
    # Note: hierarchy pages are now tracked in state and deleted in step 2.
    # This step handles any remaining hierarchy root pages not caught by state.
    ccfm_example_id = _find_page_by_title_in_space(domain, auth, space_id, "CCFM Example")
    if ccfm_example_id:
        _delete_all_children(domain, auth, ccfm_example_id)
        _delete_page(domain, auth, ccfm_example_id, '"CCFM Example"')

    print("  ✓ _ccfm container and management page preserved for next run.")


def _get_space_id(domain, auth, space_key):
    """Return the numeric space ID for a space key, or None on failure."""
    try:
        resp = requests.get(
            f"https://{domain}/wiki/api/v2/spaces",
            params={"keys": space_key},
            auth=auth,
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0]["id"] if results else None
    except requests.RequestException:
        return None


def _find_page_by_title_in_space(domain, auth, space_id, title):
    """Find a page by exact title within a space using v2 API."""
    try:
        resp = requests.get(
            f"https://{domain}/wiki/api/v2/pages",
            params={"space-id": space_id, "title": title, "limit": 1},
            auth=auth,
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0]["id"] if results else None
    except requests.RequestException:
        return None


def _find_child_by_title(domain, auth, parent_id, title):
    """Find a direct child page of parent_id by exact title."""
    try:
        url = f"https://{domain}/wiki/api/v2/pages/{parent_id}/children"
        params: dict = {"limit": 50}
        while True:
            resp = requests.get(
                url, params=params, auth=auth, headers={"Accept": "application/json"}, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            for page in data.get("results", []):
                if page.get("title") == title:
                    return page["id"]
            next_url = data.get("_links", {}).get("next")
            if not next_url:
                break
            url = f"https://{domain}/wiki{next_url}"
            params = {}
        return None
    except requests.RequestException:
        return None


def _delete_page(domain, auth, page_id, label="page"):
    """Delete a page by ID. Accepts 404 as success."""
    url = f"https://{domain}/wiki/api/v2/pages/{page_id}"
    try:
        resp = requests.delete(url, auth=auth, timeout=15)
        if resp.status_code in (200, 204, 404):
            print(f"  ✓ Deleted {label} (ID: {page_id})")
        else:
            print(f"  ✗ Failed to delete {label} ({resp.status_code})")
    except requests.RequestException as e:
        print(f"  ✗ Error deleting {label}: {e}")


def _delete_page_by_title(domain, auth, space_id, title):
    """Find a page by title and delete it."""
    page_id = _find_page_by_title_in_space(domain, auth, space_id, title)
    if page_id:
        _delete_page(domain, auth, page_id, f'"{title}"')


def _delete_all_children(domain, auth, parent_id):
    """Recursively delete all descendants of parent_id.

    Confluence v2 API does not cascade-delete children, so nested hierarchies
    must be deleted bottom-up. This function recurses into each child before
    deleting it, ensuring grandchildren are removed first.
    """
    try:
        url = f"https://{domain}/wiki/api/v2/pages/{parent_id}/children"
        params: dict = {"limit": 50}
        children = []
        while True:
            resp = requests.get(
                url,
                params=params,
                auth=auth,
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            children.extend(data.get("results", []))
            if not data.get("_links", {}).get("next"):
                break
            url = f"https://{domain}/wiki{data['_links']['next']}"
            params = {}
        for page in children:
            _delete_all_children(domain, auth, page["id"])
            _delete_page(domain, auth, page["id"], f'"{page.get("title", page["id"])}"')
    except requests.RequestException as e:
        print(f"  ✗ Error listing children of {parent_id}: {e}")


def _list_state_property_keys(domain, auth, mgmt_page_id):
    """Return the keys of all ``ccfm-page-*`` content properties on the management page.

    Mirrors the prefix used by ``ccfm_convert.state.backend`` without importing it,
    so the smoke teardown stays decoupled from the package internals.
    """
    keys: list[str] = []
    url = f"https://{domain}/wiki/rest/api/content/{mgmt_page_id}/property"
    params: dict = {"expand": "value,version", "limit": 100}
    try:
        while True:
            resp = requests.get(
                url,
                params=params,
                auth=auth,
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for prop in data.get("results", []):
                key = prop.get("key", "")
                if _STATE_KEY_RE.match(key):
                    keys.append(key)
            next_path = data.get("_links", {}).get("next")
            if not next_path:
                break
            url = f"https://{domain}/wiki{next_path}"
            params = {}
    except requests.RequestException:
        # Best-effort cleanup — surface nothing on transient errors so the
        # session-finish hook stays quiet.
        return []
    return keys


def _reset_state(domain, auth, mgmt_page_id):
    """Delete every ``ccfm-page-*`` content property on the management page.

    The lock property (``ccfm-lock``) is left alone — if a previous run
    crashed mid-deploy and left a stale lock, run ``ccfm lock release``
    manually before the next smoke run.
    """
    keys = _list_state_property_keys(domain, auth, mgmt_page_id)
    if not keys:
        print("  ✓ State already empty (no ccfm-page-* properties)")
        return

    deleted = 0
    failed = 0
    for key in keys:
        url = f"https://{domain}/wiki/rest/api/content/{mgmt_page_id}/property/{key}"
        try:
            resp = requests.delete(url, auth=auth, timeout=15)
            if resp.status_code in (200, 204, 404):
                deleted += 1
            else:
                failed += 1
        except requests.RequestException:
            failed += 1
    if failed:
        print(f"  ✗ Reset state: {deleted} property removed, {failed} failed.")
    else:
        print(f"  ✓ State reset (removed {deleted} ccfm-page-* property/-ies).")


def _find_container_page(domain, auth, space_key):
    """Find the _ccfm container page by title (kept for backward compatibility)."""
    space_id = _get_space_id(domain, auth, space_key)
    if not space_id:
        return None
    return _find_page_by_title_in_space(domain, auth, space_id, "_ccfm")


def _load_state_pages(domain, auth, mgmt_page_id):
    """Read all ``ccfm-page-*`` content properties and assemble the path → entry map.

    Returns the ``pages`` portion of state — a dict keyed by relative path. The
    smoke teardown only needs this slice (it iterates entries to delete each
    deployed Confluence page); ``version`` and other state envelope fields are
    not required here.
    """
    pages: dict = {}
    url = f"https://{domain}/wiki/rest/api/content/{mgmt_page_id}/property"
    params: dict = {"expand": "value,version", "limit": 100}
    try:
        while True:
            resp = requests.get(
                url,
                params=params,
                auth=auth,
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for prop in data.get("results", []):
                key = prop.get("key", "")
                if not _STATE_KEY_RE.match(key):
                    continue
                value = prop.get("value")
                if not isinstance(value, dict):
                    continue
                path = value.get("path")
                if not isinstance(path, str) or not path:
                    continue
                pages[path] = {k: v for k, v in value.items() if k != "path"}
            next_path = data.get("_links", {}).get("next")
            if not next_path:
                break
            url = f"https://{domain}/wiki{next_path}"
            params = {}
    except requests.RequestException:
        # Best-effort: a transient list failure here returns an empty mapping,
        # which causes the teardown to skip page deletion for this run. The
        # next smoke run's ``_reset_state`` will still nuke the orphaned
        # ``ccfm-page-*`` properties (it deletes by key regex without
        # inspecting values), and any stranded Confluence pages will be
        # re-discovered then. Logging would clutter the session-finish hook.
        return {}
    return pages


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def smoke_creds():
    """Return Confluence credentials from environment variables.

    Skips the entire test session if any required variable is missing.
    Does NOT validate credentials against the live API — tests that require a
    live Confluence connection should also declare the ``confluence_live``
    fixture, which performs that validation.
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
def confluence_live(smoke_creds):
    """Validate that Confluence credentials work against the real API.

    Skip the test if credentials are placeholder values (copied verbatim from
    .env.smoke.example) or if the API call fails (wrong domain, expired token,
    space not found, network unavailable).

    Declare this fixture in any test that makes real Confluence API calls so
    that failures surface as clean SKIP messages instead of cascading HTTP errors.
    Tests that only use ``--dump`` or ``--plan`` (no API calls) should NOT
    declare this fixture — they run fine with any credentials.
    """
    # Known placeholder values from .env.smoke.example — never real credentials
    _PLACEHOLDER_DOMAINS = {"your-domain.atlassian.net"}
    _PLACEHOLDER_EMAILS = {"your@email.com"}
    _PLACEHOLDER_TOKENS = {"your-api-token"}

    if (
        smoke_creds["domain"] in _PLACEHOLDER_DOMAINS
        or smoke_creds["email"] in _PLACEHOLDER_EMAILS
        or smoke_creds["token"] in _PLACEHOLDER_TOKENS
    ):
        pytest.skip(
            "Smoke test credentials appear to be placeholder values from "
            ".env.smoke.example. Copy .env.smoke.example to .env.smoke, "
            "fill in real Confluence credentials, then re-run."
        )

    try:
        resp = requests.get(
            f"https://{smoke_creds['domain']}/wiki/api/v2/spaces",
            params={"keys": smoke_creds["space"]},
            auth=(smoke_creds["email"], smoke_creds["token"]),
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code == 401:
            pytest.skip(
                "Confluence credentials rejected (401 Unauthorized). "
                "Check CONFLUENCE_EMAIL and CONFLUENCE_TOKEN in .env.smoke."
            )
        if resp.status_code == 404 or not resp.json().get("results"):
            pytest.skip(
                f"Confluence space '{smoke_creds['space']}' not found at "
                f"https://{smoke_creds['domain']}. "
                "Check CONFLUENCE_DOMAIN and CCFM_SMOKE_SPACE."
            )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        pytest.skip(
            f"Cannot reach Confluence at https://{smoke_creds['domain']}. "
            "Check CONFLUENCE_DOMAIN and your network connection."
        )
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"Confluence API check failed: {exc}")


@pytest.fixture(scope="session")
def ccfm_run(smoke_creds):
    """Return a callable that invokes ccfm_convert with smoke credentials.

    Uses the subcommand CLI structure. The first positional arg should be
    the subcommand (init, plan, apply, state, lock).

    Args:
        *extra_args: CLI arguments including subcommand.
        check (bool): If True (default), raise CalledProcessError on non-zero exit.

    Returns:
        subprocess.CompletedProcess
    """

    def _run(*extra_args, check=True):
        cmd = [
            sys.executable,
            "-m",
            "ccfm_convert",
            "--domain",
            smoke_creds["domain"],
            "--email",
            smoke_creds["email"],
            "--token",
            smoke_creds["token"],
            "--space",
            smoke_creds["space"],
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


@pytest.fixture(scope="session", autouse=True)
def _require_space_initialized(smoke_creds):
    """Exit early if the CCFM space infrastructure has not been initialised.

    The ``_ccfm`` container and ``CCFM State Management`` page are one-time
    prerequisites — they must exist before any smoke test can run.  If they are
    absent, the session exits immediately with a clear error message rather than
    producing confusing test failures.

    Run once manually to initialise:

        ccfm init --domain <domain> --email <email> --token <token> --space <space>

    See README.md → "Initial Setup" for full instructions.
    """
    domain = smoke_creds.get("domain", "")
    email = smoke_creds.get("email", "")
    token = smoke_creds.get("token", "")

    if not (domain and email and token):
        # Credentials missing — existing confluence_live fixture handles this per-test.
        return

    auth = (email, token)
    space_key = smoke_creds["space"]

    space_id = _get_space_id(domain, auth, space_key)
    if not space_id:
        return  # Network/credential issue — let individual tests fail with context.

    container_id = _find_page_by_title_in_space(domain, auth, space_id, "_ccfm")
    if not container_id:
        pytest.exit(
            f"\n\nCCFM space '{space_key}' is not initialised.\n"
            "Run `ccfm init` to create the required management infrastructure:\n\n"
            f"    ccfm --domain {domain} --email {email} "
            "--token <token> --space " + space_key + " init\n\n"
            "See README.md → 'Initial Setup' for full instructions.\n",
            returncode=1,
        )

    mgmt_page_id = _find_child_by_title(domain, auth, container_id, "CCFM State Management")
    if not mgmt_page_id:
        pytest.exit(
            f"\n\nCCFM space '{space_key}' is partially initialised "
            "(_ccfm container found but CCFM State Management page is missing).\n"
            "Re-run `ccfm init` to repair the infrastructure:\n\n"
            f"    ccfm --domain {domain} --email {email} "
            "--token <token> --space " + space_key + " init\n\n"
            "See README.md → 'Initial Setup' for full instructions.\n",
            returncode=1,
        )


@pytest.fixture(scope="session")
def smoke_docs():
    """Return the root path of the smoke test fixture docs."""
    return SMOKE_DOCS
