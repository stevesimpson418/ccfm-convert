"""Tests for main.py CLI module (subcommand-based CLI)."""

import json
import os
from argparse import Namespace
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import ccfm_convert.main as main
from ccfm_convert.main import _derive_title, _rel_path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_api():
    """Create mock API with common defaults."""
    api = Mock()
    api.get_space_id = Mock(return_value="space123")
    api.find_page_by_title = Mock(return_value="container-id")
    api.find_child_page_by_title = Mock(return_value="mgmt-page-id")
    api.create_page = Mock(return_value="page123")
    api.update_page = Mock()
    api.add_labels = Mock()
    return api


def _base_plan_argv(docs_root, *, extra=None):
    """Build a standard plan sys.argv list."""
    argv = [
        "main.py",
        "--domain",
        "example.atlassian.net",
        "--email",
        "test@example.com",
        "--token",
        "token",
        "--space",
        "TEST",
        "plan",
        "--docs-root",
        str(docs_root),
    ]
    if extra:
        argv.extend(extra)
    return argv


def _base_apply_argv(docs_root, *, extra=None):
    """Build a standard apply sys.argv list with --auto-approve by default."""
    argv = [
        "main.py",
        "--domain",
        "example.atlassian.net",
        "--email",
        "test@example.com",
        "--token",
        "token",
        "--space",
        "TEST",
        "apply",
        "--auto-approve",
        "--docs-root",
        str(docs_root),
    ]
    if extra:
        argv.extend(extra)
    return argv


def _base_init_argv():
    """Build a standard init sys.argv list."""
    return [
        "main.py",
        "--domain",
        "example.atlassian.net",
        "--email",
        "test@example.com",
        "--token",
        "token",
        "--space",
        "TEST",
        "init",
    ]


def _base_state_argv(subcommand, extra=None):
    """Build a standard state sys.argv list."""
    argv = [
        "main.py",
        "--domain",
        "example.atlassian.net",
        "--email",
        "test@example.com",
        "--token",
        "token",
        "--space",
        "TEST",
        "state",
        subcommand,
    ]
    if extra:
        argv.extend(extra)
    return argv


def _base_lock_argv(subcommand):
    """Build a standard lock sys.argv list."""
    return [
        "main.py",
        "--domain",
        "example.atlassian.net",
        "--email",
        "test@example.com",
        "--token",
        "token",
        "--space",
        "TEST",
        "lock",
        subcommand,
    ]


def _mock_plan_with_changes(files=None):
    """Create a mock plan that reports has_changes=True with actionable page_actions."""
    plan = Mock()
    plan.has_changes.return_value = True
    plan.destroy_actions = []
    if files:
        actions = []
        for f in files:
            action = Mock()
            action.action = "add"
            action.filepath = f
            actions.append(action)
        plan.page_actions = actions
    else:
        action = Mock()
        action.action = "add"
        action.filepath = Path("/tmp/fake.md")
        plan.page_actions = [action]
    return plan


def _mock_plan_no_changes():
    """Create a mock plan that reports has_changes=False."""
    plan = Mock()
    plan.has_changes.return_value = False
    plan.destroy_actions = []
    plan.page_actions = []
    return plan


# ---------------------------------------------------------------------------
# _rel_path helper
# ---------------------------------------------------------------------------


class TestRelPath:
    def test_rel_path_returns_relative_string_when_under_cwd(self, tmp_path):
        """Returns relative path string when filepath is under cwd."""
        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            f = tmp_path / "docs" / "page.md"
            result = _rel_path(f)
            assert result == "docs/page.md"
        finally:
            os.chdir(original)

    def test_rel_path_returns_absolute_string_when_outside_cwd(self):
        """Returns absolute path string when filepath is not under cwd."""
        f = Path("/some/absolute/path/file.md")
        result = _rel_path(f)
        assert result == "/some/absolute/path/file.md"


# ---------------------------------------------------------------------------
# _derive_title helper
# ---------------------------------------------------------------------------


class TestDeriveTitle:
    def test_returns_frontmatter_title(self, tmp_path):
        """Returns frontmatter title when page_meta.title is present."""
        f = tmp_path / "my-page.md"
        f.write_text("---\npage_meta:\n  title: Custom Title\n---\n# Content")
        assert _derive_title(f) == "Custom Title"

    def test_falls_back_to_stem_when_no_frontmatter(self, tmp_path):
        """Returns stem-derived title when frontmatter has no title."""
        f = tmp_path / "my-page.md"
        f.write_text("# Content without frontmatter")
        assert _derive_title(f) == "My Page"

    def test_falls_back_to_stem_on_read_error(self, tmp_path):
        """Returns stem-derived title when file cannot be read."""
        f = tmp_path / "unreadable-doc.md"
        # Don't create the file — read_text will raise OSError
        assert _derive_title(f) == "Unreadable Doc"


# ---------------------------------------------------------------------------
# CLI argument parsing and no-subcommand
# ---------------------------------------------------------------------------


class TestCLIArguments:
    """Test CLI argument parsing and routing."""

    def test_no_subcommand_exits_with_error(self):
        """No subcommand prints help and exits 1."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["main.py"]):
                main.main()
        assert exc_info.value.code == 1

    def test_missing_credentials_exits_with_error_plan(self, tmp_path):
        """Missing required credentials cause SystemExit for plan."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                ["main.py", "plan", "--docs-root", str(docs)],
            ):
                main.main()

    def test_missing_credentials_exits_with_error_apply(self, tmp_path):
        """Missing required credentials cause SystemExit for apply."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                ["main.py", "apply", "--docs-root", str(docs), "--auto-approve"],
            ):
                main.main()


class TestDomainNormalization:
    """Test _normalize_domain strips protocol prefixes and trailing slashes."""

    def test_https_prefix_is_stripped(self):
        """https:// prefix is removed from domain."""
        args = Namespace(domain="https://company.atlassian.net")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_http_prefix_is_stripped(self):
        """http:// prefix is removed from domain."""
        args = Namespace(domain="http://company.atlassian.net")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_trailing_slash_is_stripped(self):
        """Trailing slashes are removed from domain."""
        args = Namespace(domain="company.atlassian.net/")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_https_with_trailing_slash_both_stripped(self):
        """Both protocol prefix and trailing slash are removed."""
        args = Namespace(domain="https://company.atlassian.net/")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_bare_domain_is_unchanged(self):
        """Domain without protocol or slash passes through unchanged."""
        args = Namespace(domain="company.atlassian.net")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_none_domain_is_unchanged(self):
        """None domain (not yet provided) does not raise."""
        args = Namespace(domain=None)
        main._normalize_domain(args)
        assert args.domain is None

    def test_empty_string_domain_is_unchanged(self):
        """Empty string domain passes through unchanged."""
        args = Namespace(domain="")
        main._normalize_domain(args)
        assert args.domain == ""

    def test_uppercase_https_prefix_is_stripped(self):
        """HTTPS:// prefix (uppercase) is removed from domain."""
        args = Namespace(domain="HTTPS://company.atlassian.net")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_mixed_case_http_prefix_is_stripped(self):
        """Http:// prefix (mixed case) is removed from domain."""
        args = Namespace(domain="Http://company.atlassian.net")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    def test_path_after_host_is_stripped(self):
        """Path components after the hostname are removed."""
        args = Namespace(domain="https://company.atlassian.net/wiki")
        main._normalize_domain(args)
        assert args.domain == "company.atlassian.net"

    @patch("ccfm_convert.main.init_remote_state")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_init_normalizes_domain_with_https(self, mock_api_class, mock_init, capsys):
        """End-to-end: init subcommand strips https:// before creating API."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        with patch(
            "sys.argv",
            [
                "main.py",
                "--domain",
                "https://example.atlassian.net",
                "--email",
                "test@example.com",
                "--token",
                "tok",
                "--space",
                "TEST",
                "init",
            ],
        ):
            main.main()

        mock_api_class.assert_called_once_with("example.atlassian.net", "test@example.com", "tok")


# ---------------------------------------------------------------------------
# Init subcommand
# ---------------------------------------------------------------------------


class TestInitSubcommand:
    """Test the 'init' subcommand."""

    @patch("ccfm_convert.main.init_remote_state")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_init_calls_init_remote_state(self, mock_api_class, mock_init, capsys):
        """init subcommand creates API and calls init_remote_state."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        with patch("sys.argv", _base_init_argv()):
            main.main()

        mock_init.assert_called_once_with(mock_api, "TEST", "space123")
        captured = capsys.readouterr()
        assert "Initialization complete" in captured.out

    @patch("ccfm_convert.main.init_remote_state")
    @patch("ccfm_convert.main.ConfluenceAPI")
    @patch("sys.stdout", new_callable=StringIO)
    def test_init_prints_space_lookup(self, mock_stdout, mock_api_class, mock_init):
        """init prints the space lookup message."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        with patch("sys.argv", _base_init_argv()):
            main.main()

        output = mock_stdout.getvalue()
        assert "Looking up space: TEST" in output

    @patch("ccfm_convert.main.init_remote_state")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_init_prints_destroy_warning(self, mock_api_class, mock_init, capsys):
        """init prints the destroy warning message."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        with patch("sys.argv", _base_init_argv()):
            main.main()

        captured = capsys.readouterr()
        assert "destroy operations" in captured.out
        assert "Removing files or folders" in captured.out


# ---------------------------------------------------------------------------
# Plan subcommand
# ---------------------------------------------------------------------------


class TestPlanSubcommand:
    """Test the 'plan' subcommand."""

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_no_changes_exits_zero(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """plan with no changes returns normally (no sys.exit call)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = _mock_plan_no_changes()
        mock_compute_plan.return_value = mock_plan

        # Should NOT raise SystemExit — just returns normally
        with patch("sys.argv", _base_plan_argv(docs)):
            main.main()

        mock_compute_plan.assert_called_once()
        mock_plan.print_summary.assert_called_once()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_has_changes_returns_normally(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """plan with changes returns normally (no sys.exit)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = _mock_plan_with_changes()
        mock_compute_plan.return_value = mock_plan

        # Should NOT raise SystemExit
        with patch("sys.argv", _base_plan_argv(docs)):
            main.main()

        mock_compute_plan.assert_called_once()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_exit_code_has_changes_exits_two(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """--plan-exit-code exits 2 when there are pending changes."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = _mock_plan_with_changes()
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                _base_plan_argv(docs, extra=["--plan-exit-code"]),
            ):
                main.main()

        assert exc_info.value.code == 2

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_exit_code_no_changes_exits_zero(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """--plan-exit-code exits 0 when there are no changes."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = _mock_plan_no_changes()
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                _base_plan_argv(docs, extra=["--plan-exit-code"]),
            ):
                main.main()

        assert exc_info.value.code == 0

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_with_docs_root_excludes_page_content_md(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """plan with --docs-root excludes .page_content.md files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# A")
        (docs / ".page_content.md").write_text("# Container")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_compute_plan.return_value = _mock_plan_no_changes()

        with patch("sys.argv", _base_plan_argv(docs)):
            main.main()

        call_kwargs = mock_compute_plan.call_args[1]
        files = call_kwargs["files"]
        assert all(f.name != ".page_content.md" for f in files)

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_no_lock_acquired(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """plan does NOT instantiate LockManager."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_compute_plan.return_value = _mock_plan_no_changes()

        with patch("sys.argv", _base_plan_argv(docs)):
            main.main()

        mock_lock_class.assert_not_called()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_force_flag_passed_to_compute_plan(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """--force is passed to compute_plan."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "test.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_compute_plan.return_value = _mock_plan_no_changes()

        with patch("sys.argv", _base_plan_argv(docs, extra=["--force"])):
            main.main()

        call_kwargs = mock_compute_plan.call_args[1]
        assert call_kwargs["force"] is True

    def test_plan_no_docs_root_exits(self, tmp_path, monkeypatch):
        """plan without --docs-root (and no config) exits 1."""
        monkeypatch.chdir(tmp_path)  # ensure no ccfm.yaml found
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "token",
                    "--space",
                    "TEST",
                    "plan",
                ],
            ):
                main.main()


# ---------------------------------------------------------------------------
class TestDocsRootConfig:
    """Test that docs_root from config is used correctly."""

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_uses_docs_root_from_config(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """plan uses docs_root from ccfm.yaml config."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "page.md").write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_compute_plan.return_value = _mock_plan_no_changes()

        config_file = tmp_path / "ccfm.yaml"
        config_file.write_text(
            f"version: 1\ndomain: d.atlassian.net\nemail: e@e.com\nspace: S\ndocs_root: {docs_dir}\n"
        )

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("sys.argv", ["main.py", "--token", "tok", "plan"]):
                main.main()
        finally:
            os.chdir(original)

        mock_compute_plan.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_apply_uses_docs_root_from_config(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """apply uses docs_root from config and dispatches to deploy_tree."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        test_file = docs_dir / "page.md"
        test_file.write_text("---\npage_meta:\n  title: Test\n---\n# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_plan = _mock_plan_with_changes([test_file])
        mock_compute_plan.return_value = mock_plan

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        config_file = tmp_path / "ccfm.yaml"
        config_file.write_text(
            f"version: 1\ndomain: d.atlassian.net\nemail: e@e.com\nspace: S\ndocs_root: {docs_dir}\n"
        )

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("sys.argv", ["main.py", "--token", "tok", "apply", "--auto-approve"]):
                main.main()
        finally:
            os.chdir(original)

        mock_deploy_tree.assert_called_once()

    def test_resolve_target_files_uses_docs_root(self, tmp_path):
        """_resolve_target_files uses docs_root and excludes .page_content.md."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "page.md").write_text("# Test")
        (docs_dir / ".page_content.md").write_text("# Container")

        args = Namespace(docs_root=docs_dir)
        result = main._resolve_target_files(args)
        assert len(result) == 1
        assert result[0].name == "page.md"

    def test_resolve_target_files_exits_when_no_docs_root(self):
        """Exits with error when docs_root is None."""
        args = Namespace(docs_root=None)
        with pytest.raises(SystemExit):
            main._resolve_target_files(args)

    def test_resolve_target_files_exits_when_docs_root_missing(self, tmp_path):
        """Exits with error when docs_root directory does not exist."""
        args = Namespace(docs_root=tmp_path / "nonexistent")
        with pytest.raises(SystemExit):
            main._resolve_target_files(args)


# ---------------------------------------------------------------------------
# Debug file (ADF inspection)
# ---------------------------------------------------------------------------


class TestDebugFile:
    """Test --debug-file on plan subcommand (ADF inspection, no API calls)."""

    def test_debug_file_prints_adf_json(self, tmp_path, capsys):
        """--debug-file outputs valid ADF JSON to stdout."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Hello World")

        with patch(
            "sys.argv",
            ["main.py", "plan", "--debug-file", str(test_file)],
        ):
            main.main()

        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["type"] == "doc"

    def test_debug_file_missing_file_error(self, tmp_path):
        """--debug-file with non-existent file exits with error."""
        missing = tmp_path / "nope.md"
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                ["main.py", "plan", "--debug-file", str(missing)],
            ):
                main.main()

    def test_debug_file_with_ci_banner(self, tmp_path, capsys):
        """--debug-file applies CI banner when enabled in frontmatter."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        with patch(
            "sys.argv",
            [
                "main.py",
                "plan",
                "--debug-file",
                str(test_file),
                "--git-repo-url",
                "https://github.com/org/repo",
            ],
        ):
            main.main()

        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["type"] == "doc"
        # CI banner is the first content node
        first_content = data["content"][0]
        assert first_content["type"] == "panel"

    def test_debug_file_no_api_calls(self, tmp_path, capsys):
        """--debug-file does not require credentials or API calls."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        # No --domain, --email, --token, --space provided — should still work
        with patch(
            "sys.argv",
            ["main.py", "plan", "--debug-file", str(test_file)],
        ):
            main.main()

        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["type"] == "doc"

    def test_debug_file_ci_banner_disabled(self, tmp_path, capsys):
        """--debug-file respects ci_banner: false in frontmatter."""
        test_file = tmp_path / "test.md"
        test_file.write_text("---\ndeploy_config:\n  ci_banner: false\n---\n# Test")

        with patch(
            "sys.argv",
            ["main.py", "plan", "--debug-file", str(test_file)],
        ):
            main.main()

        output = capsys.readouterr().out
        data = json.loads(output)
        # First content should be heading, not expand (no CI banner)
        assert data["content"][0]["type"] == "heading"


# ---------------------------------------------------------------------------
# Apply subcommand — directory deployment
# ---------------------------------------------------------------------------


class TestApplyDocsRoot:
    """Test docs_root deployment via apply (with lock)."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_directory_deployment(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Apply a directory: calls deploy_tree."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        f1 = test_dir / "page.md"
        f1.write_text("# Page")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_compute_plan.return_value = _mock_plan_with_changes([f1])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(test_dir)):
            main.main()

        mock_deploy_tree.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_saved_for_each_deployed_page_in_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """state.set_page is called for each page_id returned from deploy_tree."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f1 = docs / "page1.md"
        f2 = docs / "page2.md"
        f1.write_text("# P1")
        f2.write_text("# P2")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([(f1, "pid1"), (f2, "pid2")], [])

        mock_compute_plan.return_value = _mock_plan_with_changes([f1, f2])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        assert mock_state.set_page.call_count == 2
        assert mock_state.save.call_count == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_hierarchy_pages_tracked_in_state_for_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Hierarchy container pages returned by deploy_tree are saved to state."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f1 = docs / "page.md"
        f1.write_text("# P")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = (
            [(f1, "pid1")],
            [("docs/sub", "sub-pid", "Sub")],
        )

        mock_compute_plan.return_value = _mock_plan_with_changes([f1])

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        # 1 hierarchy page + 1 content page
        assert mock_state.set_page.call_count == 2
        hierarchy_call = mock_state.set_page.call_args_list[0]
        assert hierarchy_call.kwargs["rel_path"] == "docs/sub"
        assert hierarchy_call.kwargs["content_hash"] == ""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_skips_none_page_ids_in_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """page_id=None entries from deploy_tree are not written to state."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f1 = docs / "deployed.md"
        f2 = docs / "skipped.md"
        f1.write_text("# D")
        f2.write_text("# S")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([(f1, "pid-ok"), (f2, None)], [])

        mock_compute_plan.return_value = _mock_plan_with_changes([f1, f2])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        assert mock_state.set_page.call_count == 1
        assert mock_state.save.call_count == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_tree_with_git_repo_url(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--git-repo-url is passed through to deploy_tree."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        f1 = test_dir / "page.md"
        f1.write_text("# Page")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_compute_plan.return_value = _mock_plan_with_changes([f1])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        git_url = "https://github.com/user/repo"
        with patch(
            "sys.argv",
            _base_apply_argv(
                test_dir,
                extra=["--git-repo-url", git_url],
            ),
        ):
            main.main()

        mock_deploy_tree.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_apply_force_flag_passed_to_compute_plan(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--force is passed to compute_plan on apply."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        f1 = test_dir / "page.md"
        f1.write_text("# Page")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_compute_plan.return_value = _mock_plan_with_changes([f1])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_apply_argv(test_dir, extra=["--force"]),
        ):
            main.main()

        call_kwargs = mock_compute_plan.call_args[1]
        assert call_kwargs["force"] is True


# ---------------------------------------------------------------------------
# Apply subcommand — confirmation prompt
# ---------------------------------------------------------------------------


class TestApplyConfirmation:
    """Test apply confirmation prompt behavior."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_auto_approve_skips_prompt(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--auto-approve does not call input()."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("builtins.input") as mock_input:
            with patch("sys.argv", _base_apply_argv(docs)):
                main.main()

            mock_input.assert_not_called()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_non_tty_without_auto_approve_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
        capsys,
    ):
        """Non-TTY stdin without --auto-approve exits 1."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        # argv WITHOUT --auto-approve
        argv = [
            "main.py",
            "--domain",
            "example.atlassian.net",
            "--email",
            "test@example.com",
            "--token",
            "token",
            "--space",
            "TEST",
            "apply",
            "--docs-root",
            str(docs),
        ]

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = False
                with patch("sys.argv", argv):
                    main.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--auto-approve" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_tty_prompt_accepted(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """'yes' input at TTY prompt proceeds with apply."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        argv = [
            "main.py",
            "--domain",
            "example.atlassian.net",
            "--email",
            "test@example.com",
            "--token",
            "token",
            "--space",
            "TEST",
            "apply",
            "--docs-root",
            str(docs),
        ]

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="yes"):
                with patch("sys.argv", argv):
                    main.main()

        # Deploy should proceed
        mock_lock.acquire.assert_called_once()
        mock_state.save.assert_called_once()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_tty_prompt_rejected(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
        capsys,
    ):
        """'no' input at TTY prompt cancels and prints 'Apply cancelled.'."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        argv = [
            "main.py",
            "--domain",
            "example.atlassian.net",
            "--email",
            "test@example.com",
            "--token",
            "token",
            "--space",
            "TEST",
            "apply",
            "--docs-root",
            str(docs),
        ]

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="no"):
                with patch("sys.argv", argv):
                    main.main()

        captured = capsys.readouterr()
        assert "Apply cancelled." in captured.out

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_no_changes_skips_prompt(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
        capsys,
    ):
        """When plan has no changes, no prompt is shown."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_no_changes()

        argv = [
            "main.py",
            "--domain",
            "example.atlassian.net",
            "--email",
            "test@example.com",
            "--token",
            "token",
            "--space",
            "TEST",
            "apply",
            "--docs-root",
            str(docs),
        ]

        with patch("builtins.input") as mock_input:
            with patch("sys.argv", argv):
                main.main()

            mock_input.assert_not_called()

        captured = capsys.readouterr()
        assert "No changes to apply." in captured.out


# ---------------------------------------------------------------------------
# Apply subcommand — destroy handling
# ---------------------------------------------------------------------------


class TestApplyDestroy:
    """Test apply destroy page behavior."""

    @patch("ccfm_convert.main.destroy_pages")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_apply_calls_destroy_pages_when_destroys_exist(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_destroy_pages,
        tmp_path,
        capsys,
    ):
        """destroy_pages is called when plan has destroy actions."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = Mock()
        mock_plan.has_changes.return_value = True
        # No actionable page_actions (all no-op), but has destroy actions
        noop_action = Mock()
        noop_action.action = "no-op"
        mock_plan.page_actions = [noop_action]
        destroy_action = Mock()
        destroy_action.rel_path = "docs/deleted.md"
        destroy_action.page_id = "orphan-pid"
        destroy_action.title = "Deleted"
        mock_plan.destroy_actions = [destroy_action]
        mock_compute_plan.return_value = mock_plan

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        mock_destroy_pages.assert_called_once_with(mock_api, mock_state, [destroy_action])
        captured = capsys.readouterr()
        assert "Destroying 1 page(s)" in captured.out

    @patch("ccfm_convert.main.destroy_pages")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_apply_no_destroys_skips_destroy(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_destroy_pages,
        tmp_path,
    ):
        """destroy_pages is not called when plan has no destroy actions."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = _mock_plan_with_changes([test_file])
        mock_plan.destroy_actions = []
        mock_compute_plan.return_value = mock_plan

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        mock_destroy_pages.assert_not_called()


# ---------------------------------------------------------------------------
# Apply subcommand — locking
# ---------------------------------------------------------------------------


class TestApplyLocking:
    """Test apply lock acquisition and release."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_error_exits_with_code_1(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """LockError during acquire exits with code 1."""
        from ccfm_convert.state import LockError

        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock.acquire.side_effect = LockError("State is locked")
        mock_lock_class.return_value = mock_lock

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_apply_argv(docs)):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree", side_effect=RuntimeError("deploy failed"))
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_released_even_on_deploy_error(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Lock is released in finally block even when deploy raises."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with pytest.raises(RuntimeError):
            with patch("sys.argv", _base_apply_argv(docs)):
                main.main()

        mock_lock.release.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_id_passed_to_acquire(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--lock-id is forwarded to lock_mgr.acquire."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_apply_argv(
                test_file,
                extra=["--lock-id", "ci-run-42"],
            ),
        ):
            main.main()

        mock_lock.acquire.assert_called_once_with(operation="apply", lock_id="ci-run-42")


# ---------------------------------------------------------------------------
# Apply subcommand — management page not found
# ---------------------------------------------------------------------------


class TestManagementPageDiscovery:
    """Test _find_management_page discovery."""

    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_find_management_page_exits_when_container_missing(self, mock_api_class, tmp_path):
        """_find_management_page exits 1 when _ccfm container page is not found."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api.find_page_by_title.return_value = None  # container not found
        mock_api_class.return_value = mock_api

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_apply_argv(docs)):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_find_management_page_exits_when_child_missing(self, mock_api_class, tmp_path):
        """_find_management_page exits 1 when container exists but management page child missing."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api.find_page_by_title.return_value = "container-id"
        mock_api.find_child_page_by_title.return_value = None  # management page not found
        mock_api_class.return_value = mock_api

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_apply_argv(docs)):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_find_management_page_returns_page_id(
        self,
        mock_api_class,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """_find_management_page returns page_id when container->child lookup succeeds."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api.find_page_by_title.return_value = "container-id"
        mock_api.find_child_page_by_title.return_value = "found-mgmt-id"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        # ConfluenceBackend should have been called with the found mgmt page id
        mock_backend_class.assert_called_once_with(mock_api, "found-mgmt-id")


# ---------------------------------------------------------------------------
# Apply subcommand — output
# ---------------------------------------------------------------------------


class TestApplyOutput:
    """Test apply CLI output messages."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    @patch("sys.stdout", new_callable=StringIO)
    def test_success_output(
        self,
        mock_stdout,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Success message output includes 'Apply complete'."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        output = mock_stdout.getvalue()
        assert "Apply complete" in output

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    @patch("sys.stdout", new_callable=StringIO)
    def test_space_id_printed(
        self,
        mock_stdout,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Space ID is printed during apply."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        output = mock_stdout.getvalue()
        assert "Space ID: space123" in output


# ---------------------------------------------------------------------------
# Apply subcommand — error handling
# ---------------------------------------------------------------------------


class TestApplyErrorHandling:
    """Test error handling during apply."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_invalid_space(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """ValueError from get_space_id propagates."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.side_effect = ValueError("Space not found")
        mock_api_class.return_value = mock_api

        with pytest.raises(ValueError):
            with patch("sys.argv", _base_apply_argv(docs)):
                main.main()

    def test_apply_missing_file_exits(self, tmp_path):
        """Apply with --file pointing to nonexistent file exits 1."""
        missing = tmp_path / "nonexistent.md"
        with pytest.raises(SystemExit):
            with patch("sys.argv", _base_apply_argv(missing)):
                main.main()

    def test_apply_missing_directory_exits(self, tmp_path):
        """Apply with --directory pointing to nonexistent dir exits 1."""
        missing_dir = tmp_path / "no-such-dir"
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "token",
                    "--space",
                    "TEST",
                    "apply",
                    "--docs-root",
                    str(missing_dir),
                    "--auto-approve",
                ],
            ):
                main.main()

    def test_apply_no_docs_root_exits(self, tmp_path, monkeypatch):
        """Apply without --docs-root (and no config) exits 1."""
        monkeypatch.chdir(tmp_path)  # ensure no ccfm.yaml found
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "token",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                ],
            ):
                main.main()


# ---------------------------------------------------------------------------
# State subcommand
# ---------------------------------------------------------------------------


class TestStateSubcommand:
    """Test the 'state' subcommand."""

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_list_with_pages(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        capsys,
    ):
        """state list prints tracked pages."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.all_pages = {
            "docs/page.md": {
                "page_id": "pid1",
                "title": "Page",
                "deployed_at": "2026-01-01T00:00:00",
            }
        }
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_state_argv("list")):
            main.main()

        captured = capsys.readouterr()
        assert "Tracked pages (1)" in captured.out
        assert "docs/page.md" in captured.out
        assert "pid1" in captured.out

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_list_empty(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        capsys,
    ):
        """state list with no pages prints empty message."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.all_pages = {}
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_state_argv("list")):
            main.main()

        captured = capsys.readouterr()
        assert "No pages tracked in state" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_rm_removes_entry(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        capsys,
    ):
        """state rm removes the specified path from state with lock acquired."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.get_page.return_value = {"page_id": "pid1", "title": "Page"}
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_state_argv("rm", extra=["docs/page.md"])):
            main.main()

        mock_lock.acquire.assert_called_once_with(operation="state-rm")
        mock_lock.release.assert_called_once()
        mock_state.remove_page.assert_called_once_with("docs/page.md")
        mock_state.save.assert_called_once()
        captured = capsys.readouterr()
        assert "Removed 'docs/page.md' from state" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_rm_exits_when_locked(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
    ):
        """state rm exits 1 if the space is already locked."""
        from ccfm_convert.state.lock import LockError

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.get_page.return_value = {"page_id": "pid1", "title": "Page"}
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock.acquire.side_effect = LockError("locked by CI")
        mock_lock_class.return_value = mock_lock

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("rm", extra=["docs/page.md"])):
                main.main()

        assert exc_info.value.code == 1
        mock_lock.release.assert_not_called()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_rm_unknown_path_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
    ):
        """state rm with unknown path exits 1."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.get_page.return_value = None
        mock_state_class.return_value = mock_state

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("rm", extra=["nonexistent.md"])):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_pull_prints_json(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        capsys,
    ):
        """state pull prints the raw state JSON to stdout."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.raw_state = {"version": "1", "pages": {"docs/a.md": {"page_id": "p1"}}}
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_state_argv("pull")):
            main.main()

        captured = capsys.readouterr()
        assert '"version"' in captured.out
        assert '"pages"' in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_overwrites_state(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        capsys,
        tmp_path,
    ):
        """state push uploads the given JSON file as new remote state."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_backend = Mock()
        mock_backend_class.return_value = mock_backend
        mock_state_class.return_value = Mock(raw_state={})
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        state_file = tmp_path / "state.json"
        state_file.write_text('{"version": "1", "pages": {}}')

        with patch("sys.argv", _base_state_argv("push", extra=[str(state_file)])):
            main.main()

        mock_backend.save.assert_called_once_with({"version": "1", "pages": {}})
        mock_lock.acquire.assert_called_once()
        mock_lock.release.assert_called_once()
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "updated" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_exits_when_locked(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """state push exits 1 if the space is already locked."""
        from ccfm_convert.state.lock import LockError

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_state_class.return_value = Mock(raw_state={})

        mock_lock = Mock()
        mock_lock.acquire.side_effect = LockError("locked by CI")
        mock_lock_class.return_value = mock_lock

        state_file = tmp_path / "state.json"
        state_file.write_text('{"version": "1", "pages": {}}')

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("push", extra=[str(state_file)])):
                main.main()

        assert exc_info.value.code == 1
        mock_lock.release.assert_not_called()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_pages_not_dict_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """state push exits 1 when 'pages' key is not a dict."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_state_class.return_value = Mock()

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"version": "1", "pages": []}')

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("push", extra=[str(bad_file)])):
                main.main()

        assert exc_info.value.code == 1
        mock_lock.acquire.assert_not_called()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_invalid_json_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """state push with malformed JSON exits 1."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_state_class.return_value = Mock()

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not-json")

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("push", extra=[str(bad_file)])):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_invalid_schema_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """state push with missing required keys exits 1."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_state_class.return_value = Mock()

        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"only_key": true}')

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("push", extra=[str(bad_file)])):
                main.main()

        assert exc_info.value.code == 1

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../admin",  # path traversal
            "0",  # zero is not a valid Confluence page ID
            "007",  # leading zeros rejected
            "",  # empty string
            12345,  # JSON integer (not a string) — exercises isinstance(pid, str) branch
            None,  # JSON null — exercises isinstance(pid, str) branch
        ],
    )
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_invalid_page_id_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
        bad_id,
    ):
        """state push exits 1 when a page entry has an invalid page_id."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_state_class.return_value = Mock()

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps({"version": "1", "pages": {"docs/a.md": {"page_id": bad_id}}})
        )

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("push", extra=[str(bad_file)])):
                main.main()

        assert exc_info.value.code == 1
        mock_lock.acquire.assert_not_called()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_push_long_key_truncated_in_error(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
        capsys,
    ):
        """state push error message truncates oversized dict keys to 200 chars."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_state_class.return_value = Mock()
        mock_lock_class.return_value = Mock()

        long_key = "x" * 300
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps({"version": "1", "pages": {long_key: {"page_id": "../../admin"}}})
        )

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("push", extra=[str(bad_file)])):
                main.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "x" * 200 in captured.out
        assert "x" * 201 not in captured.out

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_show_prints_entry(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
        capsys,
    ):
        """state show prints JSON for the requested path."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.get_page.return_value = {
            "page_id": "pid1",
            "title": "My Page",
            "space_key": "TEST",
            "space_id": "s1",
            "content_hash": "sha256:abc",
            "deployed_at": "2026-01-01T00:00:00",
        }
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_state_argv("show", extra=["docs/my-page.md"])):
            main.main()

        captured = capsys.readouterr()
        assert "pid1" in captured.out
        assert "My Page" in captured.out

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_show_unknown_path_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_backend_class,
        mock_state_class,
    ):
        """state show with untracked path exits 1."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.get_page.return_value = None
        mock_state_class.return_value = mock_state

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_state_argv("show", extra=["docs/ghost.md"])):
                main.main()

        assert exc_info.value.code == 1

    def test_state_no_subcommand_exits(self):
        """state without subcommand exits 1."""
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "token",
                    "--space",
                    "TEST",
                    "state",
                ],
            ):
                main.main()

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Lock subcommand
# ---------------------------------------------------------------------------


class TestLockSubcommand:
    """Test the 'lock' subcommand."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_status_not_locked(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_lock_class,
        capsys,
    ):
        """lock status when unlocked prints 'State is not locked'."""
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        mock_lock = Mock()
        mock_info = Mock()
        mock_info.locked = False
        mock_lock.status.return_value = mock_info
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_lock_argv("status")):
            main.main()

        captured = capsys.readouterr()
        assert "State is not locked" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_status_locked(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_lock_class,
        capsys,
    ):
        """lock status when locked prints lock details."""
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        mock_lock = Mock()
        mock_info = Mock()
        mock_info.locked = True
        mock_info.owner = "user@host"
        mock_info.lock_id = "ci-42"
        mock_info.locked_at = "2026-01-01T00:00:00"
        mock_info.operation = "deploy"
        mock_lock.status.return_value = mock_info
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_lock_argv("status")):
            main.main()

        captured = capsys.readouterr()
        assert "State is locked" in captured.out
        assert "user@host" in captured.out
        assert "ci-42" in captured.out
        assert "deploy" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_status_locked_no_lock_id(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_lock_class,
        capsys,
    ):
        """lock status when locked but no lock_id omits Lock ID line."""
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        mock_lock = Mock()
        mock_info = Mock()
        mock_info.locked = True
        mock_info.owner = "user@host"
        mock_info.lock_id = ""
        mock_info.locked_at = "2026-01-01T00:00:00"
        mock_info.operation = "deploy"
        mock_lock.status.return_value = mock_info
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_lock_argv("status")):
            main.main()

        captured = capsys.readouterr()
        assert "Lock ID" not in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_release(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_lock_class,
        capsys,
    ):
        """lock release calls force_release and prints confirmation."""
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_lock_argv("release")):
            main.main()

        mock_lock.force_release.assert_called_once()
        captured = capsys.readouterr()
        assert "Lock released" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_acquire_success(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_lock_class,
        capsys,
    ):
        """lock acquire prints confirmation when lock is acquired."""
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        mock_lock = Mock()
        mock_info = Mock()
        mock_info.owner = "user@host"
        mock_info.operation = "manual"
        mock_lock.status.return_value = mock_info
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_lock_argv("acquire")):
            main.main()

        mock_lock.acquire.assert_called_once_with(operation="manual", lock_id=None)
        captured = capsys.readouterr()
        assert "user@host" in captured.out
        assert "manual" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_acquire_already_locked_exits(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_lock_class,
    ):
        """lock acquire exits 1 when already locked."""
        from ccfm_convert.state import LockError

        mock_api = Mock()
        mock_api_class.return_value = mock_api

        mock_lock = Mock()
        mock_lock.acquire.side_effect = LockError("already locked by other@host")
        mock_lock_class.return_value = mock_lock

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_lock_argv("acquire")):
                main.main()

        assert exc_info.value.code == 1

    def test_lock_no_subcommand_exits(self):
        """lock without subcommand exits 1."""
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "token",
                    "--space",
                    "TEST",
                    "lock",
                ],
            ):
                main.main()

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Config file loading
# ---------------------------------------------------------------------------


class TestConfigFileLoading:
    """Test ccfm.yaml config loading."""

    @pytest.fixture(autouse=True)
    def _clear_confluence_env(self, monkeypatch):
        """Remove CONFLUENCE_* env vars so argparse defaults don't leak."""
        monkeypatch.delenv("CONFLUENCE_DOMAIN", raising=False)
        monkeypatch.delenv("CONFLUENCE_EMAIL", raising=False)
        monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_config_file_loaded_when_ccfm_yaml_present(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """ccfm.yaml is auto-loaded if present."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        config_file = tmp_path / "ccfm.yaml"
        config_file.write_text(
            "version: 1\ndomain: config.atlassian.net\nemail: cfg@example.com\nspace: CFG\n"
        )

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--token",
                    "tok",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    str(docs),
                ],
            ):
                main.main()
        finally:
            os.chdir(original)

        mock_api_class.assert_called_once_with("config.atlassian.net", "cfg@example.com", "tok")

    @patch("ccfm_convert.main.load_config")
    def test_config_file_load_error_exits_with_code_1(self, mock_load_config, tmp_path):
        """Bad config file causes sys.exit(1)."""
        config_file = tmp_path / "ccfm.yaml"
        config_file.write_text("bad: yaml: content")
        mock_load_config.side_effect = Exception("parse error")

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            with pytest.raises(SystemExit) as exc_info:
                with patch(
                    "sys.argv",
                    [
                        "main.py",
                        "--token",
                        "tok",
                        "--config",
                        str(config_file),
                        "apply",
                        "--auto-approve",
                        "--docs-root",
                        "docs",
                    ],
                ):
                    main.main()
        finally:
            os.chdir(original)

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_explicit_config_flag_loads_named_file(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--config <path> loads the specified file."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(
            "version: 1\ndomain: custom.atlassian.net\nemail: custom@example.com\nspace: CUS\n"
        )

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            [
                "main.py",
                "--token",
                "tok",
                "--config",
                str(custom_config),
                "apply",
                "--auto-approve",
                "--docs-root",
                str(docs),
            ],
        ):
            main.main()

        mock_api_class.assert_called_once_with("custom.atlassian.net", "custom@example.com", "tok")


# ---------------------------------------------------------------------------
# Token handling
# ---------------------------------------------------------------------------


class TestTokenHandling:
    """Test API token supplied via CLI arg or CONFLUENCE_TOKEN env var."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_token_from_env_var(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Token is read from CONFLUENCE_TOKEN env var when --token is not provided."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "env-token-value"}):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    str(docs),
                ],
            ):
                main.main()

        mock_api_class.assert_called_once_with(
            "example.atlassian.net", "test@example.com", "env-token-value"
        )

    def test_missing_token_exits_with_error(self, monkeypatch, tmp_path):
        """No --token and no CONFLUENCE_TOKEN env var causes a SystemExit."""
        monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    str(docs),
                ],
            ):
                main.main()
        assert exc_info.value.code == 2  # argparse parser.error exits with code 2


# ---------------------------------------------------------------------------
# Domain and email env var fallbacks
# ---------------------------------------------------------------------------


class TestDomainEnvVarFallback:
    """Test domain supplied via CONFLUENCE_DOMAIN env var."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_domain_from_env_var(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Domain is read from CONFLUENCE_DOMAIN env var when --domain is not provided."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch.dict(os.environ, {"CONFLUENCE_DOMAIN": "env-domain.atlassian.net"}):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--email",
                    "test@example.com",
                    "--token",
                    "tok",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    str(docs),
                ],
            ):
                main.main()

        mock_api_class.assert_called_once_with(
            "env-domain.atlassian.net", "test@example.com", "tok"
        )

    def test_missing_domain_error_mentions_env_var(self, tmp_path):
        """Missing domain error message mentions CONFLUENCE_DOMAIN env var."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")
        with patch.dict(os.environ, {"CONFLUENCE_DOMAIN": ""}, clear=False):
            with pytest.raises(SystemExit):
                with patch(
                    "sys.argv",
                    [
                        "main.py",
                        "--email",
                        "test@example.com",
                        "--token",
                        "tok",
                        "--space",
                        "TEST",
                        "plan",
                        "--docs-root",
                        str(docs),
                    ],
                ):
                    main.main()


class TestEmailEnvVarFallback:
    """Test email supplied via CONFLUENCE_EMAIL env var."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_email_from_env_var(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Email is read from CONFLUENCE_EMAIL env var when --email is not provided."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch.dict(os.environ, {"CONFLUENCE_EMAIL": "env@example.com"}):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--token",
                    "tok",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    str(docs),
                ],
            ):
                main.main()

        mock_api_class.assert_called_once_with("example.atlassian.net", "env@example.com", "tok")

    def test_missing_email_error_mentions_env_var(self, tmp_path):
        """Missing email error message mentions CONFLUENCE_EMAIL env var."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")
        with patch.dict(os.environ, {"CONFLUENCE_EMAIL": ""}, clear=False):
            with pytest.raises(SystemExit):
                with patch(
                    "sys.argv",
                    [
                        "main.py",
                        "--domain",
                        "example.atlassian.net",
                        "--token",
                        "tok",
                        "--space",
                        "TEST",
                        "plan",
                        "--docs-root",
                        str(docs),
                    ],
                ):
                    main.main()


class TestAllCredentialsFromEnvVars:
    """Test all three credentials (domain, email, token) from env vars."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_all_credentials_from_env(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """All credentials resolved from env vars when no CLI args provided."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        env = {
            "CONFLUENCE_DOMAIN": "env.atlassian.net",
            "CONFLUENCE_EMAIL": "env@example.com",
            "CONFLUENCE_TOKEN": "env-token",
        }
        with patch.dict(os.environ, env):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    str(docs),
                ],
            ):
                main.main()

        mock_api_class.assert_called_once_with("env.atlassian.net", "env@example.com", "env-token")


# ---------------------------------------------------------------------------
# Path handling
# ---------------------------------------------------------------------------


class TestPathHandling:
    """Test path handling for file arguments."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_relative_path(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Relative path is accepted for --docs-root."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            docs = Path("docs")
            docs.mkdir()
            test_file = docs / "test.md"
            test_file.write_text("# Test")

            mock_api = Mock()
            mock_api.get_space_id.return_value = "space123"
            mock_api_class.return_value = mock_api

            mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

            mock_state = Mock()
            mock_state_class.return_value = mock_state
            mock_lock = Mock()
            mock_lock_class.return_value = mock_lock

            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "token",
                    "--space",
                    "TEST",
                    "apply",
                    "--auto-approve",
                    "--docs-root",
                    "docs",
                ],
            ):
                main.main()
        finally:
            os.chdir(original_cwd)

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_absolute_path(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Absolute path is accepted for --file."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_file = docs / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_with_changes([test_file])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(test_file.absolute())):
            main.main()


# ---------------------------------------------------------------------------
# Dependency ordering
# ---------------------------------------------------------------------------


class TestDependencyOrderingPlan:
    """Test that plan computes and displays dependency graph for directory deploys."""

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_directory_builds_dependency_graph(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """Plan for a directory with >1 file computes dependency graph."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fb = docs / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = docs / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_no_changes()

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_plan_argv(docs)):
            main.main()

        # compute_plan should be called
        mock_compute_plan.assert_called_once()
        # The plan should have dependency_graph set (not None)
        plan = mock_compute_plan.return_value
        assert plan.dependency_graph is not None

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_single_file_no_graph(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """Plan for a single file without --auto-deploy-deps has no dependency graph."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fa = docs / "a.md"
        fa.write_text("# Page A")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_compute_plan.return_value = _mock_plan_no_changes()

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_plan_argv(fa.absolute())):
            main.main()

        plan = mock_compute_plan.return_value
        # dependency_graph should not be set (or be None)
        assert not getattr(plan, "dependency_graph", None) or plan.dependency_graph is None


class TestDependencyOrderingApply:
    """Test that apply reorders actionable files by dependency graph."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_directory_deploy_reorders_by_dependency(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Apply reorders actionable_files by dependency graph order."""
        docs = tmp_path / "docs"
        docs.mkdir()
        # a.md links to b.md; alphabetically a comes first,
        # but dependency ordering should put b first
        fb = docs / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = docs / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([(fb, "pid-b"), (fa, "pid-a")], [])

        # Plan returns actions in alphabetical order (a, b)
        mock_compute_plan.return_value = _mock_plan_with_changes([fa, fb])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_apply_argv(docs)):
            main.main()

        # deploy_tree should be called with files reordered: b before a
        call_args = mock_deploy_tree.call_args
        files_kwarg = call_args.kwargs["files"]
        # b.md should come before a.md in the files list
        assert list(files_kwarg).index(fb) < list(files_kwarg).index(fa)
