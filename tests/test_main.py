"""Tests for main.py CLI module (subcommand-based CLI)."""

import json
import os
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


def _base_deploy_argv(tmp_file_or_dir, *, is_dir=False, extra=None):
    """Build a standard deploy sys.argv list."""
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
        "deploy",
    ]
    if is_dir:
        argv += ["--directory", str(tmp_file_or_dir)]
    else:
        argv += ["--file", str(tmp_file_or_dir)]
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

    def test_missing_credentials_exits_with_error(self, tmp_path):
        """Missing required credentials cause SystemExit."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")
        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                ["main.py", "deploy", "--file", str(test_file)],
            ):
                main.main()


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


# ---------------------------------------------------------------------------
# Deploy subcommand — dump mode
# ---------------------------------------------------------------------------


class TestDeployDumpMode:
    """Test deploy --dump (no API, no state, no lock)."""

    @patch("ccfm_convert.main.deploy_page")
    def test_dump_file_calls_deploy_page_with_dump_true(self, mock_deploy, tmp_path):
        """--dump with --file calls deploy_page(dump=True) without credentials."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        with patch(
            "sys.argv",
            [
                "main.py",
                "deploy",
                "--file",
                str(test_file),
                "--dump",
            ],
        ):
            main.main()

        mock_deploy.assert_called_once()
        assert mock_deploy.call_args[1]["dump"] is True

    @patch("ccfm_convert.main.deploy_tree")
    def test_dump_directory_calls_deploy_tree_with_dump_true(self, mock_deploy_tree, tmp_path):
        """--dump with --directory calls deploy_tree(dump=True)."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()

        with patch(
            "sys.argv",
            [
                "main.py",
                "deploy",
                "--directory",
                str(test_dir),
                "--dump",
            ],
        ):
            main.main()

        mock_deploy_tree.assert_called_once()
        assert mock_deploy_tree.call_args[1]["dump"] is True

    @patch("ccfm_convert.main.deploy_page")
    @patch("sys.stdout", new_callable=StringIO)
    def test_dump_mode_output(self, mock_stdout, mock_deploy, tmp_path):
        """Dump mode prints 'Dump mode' and does NOT print 'Deployment complete'."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        with patch(
            "sys.argv",
            [
                "main.py",
                "deploy",
                "--file",
                str(test_file),
                "--dump",
            ],
        ):
            main.main()

        output = mock_stdout.getvalue()
        assert "Dump mode" in output
        assert "Deployment complete" not in output

    @patch("ccfm_convert.main.deploy_page")
    def test_dump_mode_with_git_repo_url(self, mock_deploy, tmp_path):
        """--dump passes git_repo_url to deploy_page."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        with patch(
            "sys.argv",
            [
                "main.py",
                "deploy",
                "--file",
                str(test_file),
                "--dump",
                "--git-repo-url",
                "https://github.com/user/repo",
            ],
        ):
            main.main()

        call_args = mock_deploy.call_args[0]
        assert call_args[4] == "https://github.com/user/repo"


# ---------------------------------------------------------------------------
# Deploy subcommand — no file or directory
# ---------------------------------------------------------------------------


class TestDeployNoTarget:
    """Test deploy without --file or --directory."""

    def test_no_file_or_directory_exits_with_error(self):
        """Deploy without --file or --directory exits 1."""
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
                    "deploy",
                ],
            ):
                main.main()


# ---------------------------------------------------------------------------
# Deploy subcommand — plan mode
# ---------------------------------------------------------------------------


class TestDeployPlanMode:
    """Test deploy --plan (needs credentials + mgmt page + state, no lock)."""

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
        """--plan exits 0 when there are no pending changes."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = Mock()
        mock_plan.has_changes.return_value = False
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_deploy_argv(test_file, extra=["--plan"])):
                main.main()

        assert exc_info.value.code == 0
        mock_compute_plan.assert_called_once()
        mock_plan.print_summary.assert_called_once()

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_has_changes_exits_zero_by_default(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """--plan exits 0 even when there are pending changes (CI-friendly default)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = Mock()
        mock_plan.has_changes.return_value = True
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_deploy_argv(test_file, extra=["--plan"])):
                main.main()

        assert exc_info.value.code == 0

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
        """--plan --plan-exit-code exits 2 when there are pending changes."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = Mock()
        mock_plan.has_changes.return_value = True
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                _base_deploy_argv(
                    test_file,
                    extra=["--plan", "--plan-exit-code"],
                ),
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
        """--plan --plan-exit-code exits 0 when there are no changes."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_plan = Mock()
        mock_plan.has_changes.return_value = False
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                _base_deploy_argv(
                    test_file,
                    extra=["--plan", "--plan-exit-code"],
                ),
            ):
                main.main()

        assert exc_info.value.code == 0

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_with_archive_orphans(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """--plan --archive-orphans passes archive_orphans=True to compute_plan."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_compute_plan.return_value = Mock()

        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                _base_deploy_argv(
                    test_file,
                    extra=["--plan", "--archive-orphans"],
                ),
            ):
                main.main()

        call_kwargs = mock_compute_plan.call_args[1]
        assert call_kwargs["archive_orphans"] is True

    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.compute_plan")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_plan_with_directory_excludes_page_content_md(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_compute_plan,
        mock_backend_class,
        mock_state_class,
        tmp_path,
    ):
        """--plan with --directory excludes .page_content.md files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# A")
        (docs / ".page_content.md").write_text("# Container")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_compute_plan.return_value = Mock()

        with pytest.raises(SystemExit):
            with patch("sys.argv", _base_deploy_argv(docs, is_dir=True, extra=["--plan"])):
                main.main()

        call_kwargs = mock_compute_plan.call_args[1]
        files = call_kwargs["files"]
        assert all(f.name != ".page_content.md" for f in files)


# ---------------------------------------------------------------------------
# Deploy subcommand — live single-file deployment
# ---------------------------------------------------------------------------


class TestDeploySingleFile:
    """Test single-file live deployment (with lock)."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_single_file_deployment(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy,
        mock_hierarchy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Deploy a single file: acquires lock, deploys, saves state, releases lock."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = ("parent123", [])
        mock_deploy.return_value = "deployed-page-id"

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_file)):
            main.main()

        mock_lock.acquire.assert_called_once()
        mock_deploy.assert_called_once()
        mock_state.set_page.assert_called_once()
        mock_state.save.assert_called_once()
        mock_lock.release.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_hierarchy_pages_tracked_in_state_for_single_file(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy,
        mock_hierarchy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Hierarchy container pages returned by ensure_page_hierarchy are saved to state."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = ("parent123", [("docs/my-dir", "dir-pid", "My Dir")])
        mock_deploy.return_value = "deployed-page-id"

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_deploy_argv(test_file)):
            main.main()

        # set_page called once for the hierarchy container + once for the page itself
        assert mock_state.set_page.call_count == 2
        hierarchy_call = mock_state.set_page.call_args_list[0]
        assert hierarchy_call.kwargs["rel_path"] == "docs/my-dir"
        assert hierarchy_call.kwargs["content_hash"] == ""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_not_saved_when_deploy_returns_none(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy,
        mock_hierarchy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """state.set_page not called if deploy_page returns None; state.save always called."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None  # page skipped

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_file)):
            main.main()

        mock_state.set_page.assert_not_called()
        mock_state.save.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_file_with_custom_docs_root(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy,
        mock_hierarchy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--docs-root is passed through to ensure_page_hierarchy."""
        custom_root = tmp_path / "custom_docs"
        custom_root.mkdir()
        test_file = custom_root / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                test_file,
                extra=["--docs-root", str(custom_root)],
            ),
        ):
            main.main()

        mock_deploy.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_file_with_git_repo_url(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy,
        mock_hierarchy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--git-repo-url is passed through to deploy_page."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        git_url = "https://github.com/user/repo"
        with patch(
            "sys.argv",
            _base_deploy_argv(
                test_file,
                extra=["--git-repo-url", git_url],
            ),
        ):
            main.main()

        call_args = mock_deploy.call_args[0]
        assert call_args[4] == git_url

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_file_with_hierarchy(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy,
        mock_hierarchy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """ensure_page_hierarchy parent_id is passed to deploy_page."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)
        test_file = subdir / "page.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = ("parent123", [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                test_file,
                extra=["--docs-root", str(docs_root)],
            ),
        ):
            main.main()

        mock_hierarchy.assert_called_once()
        assert mock_deploy.call_args[0][2] == "parent123"


# ---------------------------------------------------------------------------
# Deploy subcommand — live directory deployment
# ---------------------------------------------------------------------------


class TestDeployDirectory:
    """Test directory live deployment (with lock)."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_directory_deployment(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Deploy a directory: calls deploy_tree."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_dir, is_dir=True)):
            main.main()

        mock_deploy_tree.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_saved_for_each_deployed_page_in_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
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

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(docs, is_dir=True)):
            main.main()

        assert mock_state.set_page.call_count == 2
        assert mock_state.save.call_count == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_hierarchy_pages_tracked_in_state_for_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
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

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        with patch("sys.argv", _base_deploy_argv(docs, is_dir=True)):
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
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_state_skips_none_page_ids_in_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
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

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(docs, is_dir=True)):
            main.main()

        assert mock_state.set_page.call_count == 1
        assert mock_state.save.call_count == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_tree_with_git_repo_url(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--git-repo-url is passed through to deploy_tree."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        git_url = "https://github.com/user/repo"
        with patch(
            "sys.argv",
            _base_deploy_argv(
                test_dir,
                is_dir=True,
                extra=["--git-repo-url", git_url],
            ),
        ):
            main.main()

        call_args = mock_deploy_tree.call_args[0]
        assert call_args[4] == git_url


# ---------------------------------------------------------------------------
# Deploy subcommand — --changed-only
# ---------------------------------------------------------------------------


class TestDeployChangedOnly:
    """Test deploy --changed-only."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_changed_only_prints_count_message(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
        capsys,
    ):
        """--changed-only prints the count of changed files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        changed = docs / "changed.md"
        unchanged = docs / "unchanged.md"
        changed.write_text("# New Content")
        unchanged.write_text("# Old Content")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        # State mock: changed.md has_changed=True, unchanged.md has_changed=False
        mock_state = Mock()
        mock_state.has_changed.side_effect = lambda rel, f: f.name == "changed.md"
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--changed-only"],
            ),
        ):
            main.main()

        captured = capsys.readouterr()
        assert "--changed-only: 1 file(s) with changes" in captured.out

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_zero_changes_does_not_call_deploy_tree(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
        capsys,
    ):
        """When --changed-only reports 0 changes, deploy_tree must not be called."""
        docs = tmp_path / "docs"
        docs.mkdir()
        unchanged = docs / "unchanged.md"
        unchanged.write_text("# Content")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        # All files report as unchanged
        mock_state = Mock()
        mock_state.has_changed.return_value = False
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--changed-only"],
            ),
        ):
            main.main()

        mock_deploy_tree.assert_not_called()
        mock_lock.acquire.assert_not_called()
        captured = capsys.readouterr()
        assert "No changes to deploy" in captured.out

    @patch("ccfm_convert.main.archive_page")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_zero_changes_does_not_archive_pages(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_archive,
        tmp_path,
    ):
        """When --changed-only reports 0 changes, --archive-orphans must not run."""
        docs = tmp_path / "docs"
        docs.mkdir()
        unchanged = docs / "unchanged.md"
        unchanged.write_text("# Content")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state.has_changed.return_value = False
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--changed-only", "--archive-orphans"],
            ),
        ):
            main.main()

        mock_deploy_tree.assert_not_called()
        mock_archive.assert_not_called()


# ---------------------------------------------------------------------------
# Deploy subcommand — --archive-orphans
# ---------------------------------------------------------------------------


class TestDeployArchiveOrphans:
    """Test deploy --archive-orphans during live deployment."""

    @patch("ccfm_convert.main.archive_page")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_archive_orphans_calls_archive_and_removes_from_state(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_archive,
        tmp_path,
    ):
        """Orphaned pages are archived and removed from state."""
        docs = tmp_path / "docs"
        docs.mkdir()
        active = docs / "active.md"
        active.write_text("# Active")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([(active, "active-pid")], [])

        mock_state = Mock()
        mock_state.find_orphans.return_value = ["docs/deleted.md"]
        mock_state.get_page.return_value = {"page_id": "orphan-pid", "title": "Deleted"}
        mock_state_class.return_value = mock_state

        mock_archive.return_value = True

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--archive-orphans"],
            ),
        ):
            main.main()

        mock_archive.assert_called_once_with(mock_api, "orphan-pid", "Deleted")
        mock_state.remove_page.assert_called_once_with("docs/deleted.md")

    @patch("ccfm_convert.main.archive_page")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_archive_orphans_no_orphans_prints_message(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_archive,
        tmp_path,
        capsys,
    ):
        """When no orphans found, prints info message."""
        docs = tmp_path / "docs"
        docs.mkdir()
        active = docs / "active.md"
        active.write_text("# Active")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([(active, "active-pid")], [])

        mock_state = Mock()
        mock_state.find_orphans.return_value = []
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--archive-orphans"],
            ),
        ):
            main.main()

        captured = capsys.readouterr()
        assert "No orphaned pages found" in captured.out
        mock_archive.assert_not_called()

    @patch("ccfm_convert.main.archive_page")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_archive_failure_does_not_remove_from_state(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_archive,
        tmp_path,
    ):
        """If archive_page returns False, entry stays in state."""
        docs = tmp_path / "docs"
        docs.mkdir()

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([], [])

        mock_state = Mock()
        mock_state.find_orphans.return_value = ["docs/orphan.md"]
        mock_state.get_page.return_value = {"page_id": "orphan-id", "title": "Orphan"}
        mock_state_class.return_value = mock_state

        mock_archive.return_value = False  # simulate archive failure

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--archive-orphans"],
            ),
        ):
            main.main()

        mock_archive.assert_called_once()
        mock_state.remove_page.assert_not_called()

    @patch("ccfm_convert.main.archive_page")
    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_tree")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_changed_only_with_archive_orphans_uses_all_files(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_deploy_tree,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        mock_archive,
        tmp_path,
    ):
        """--changed-only + --archive-orphans: orphan detection uses all disk files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        changed = docs / "changed.md"
        unchanged = docs / "unchanged.md"
        changed.write_text("# New Content")
        unchanged.write_text("# Stable Content")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = ([(changed, "changed-pid")], [])

        mock_state = Mock()
        mock_state.has_changed.side_effect = lambda rel, f: "changed" in str(f)
        mock_state.find_orphans.return_value = []
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                docs,
                is_dir=True,
                extra=["--changed-only", "--archive-orphans"],
            ),
        ):
            main.main()

        # find_orphans should receive all_files (both changed and unchanged)
        call_args = mock_state.find_orphans.call_args[0]
        all_files_passed = call_args[0]
        filenames = {f.name for f in all_files_passed}
        assert "changed.md" in filenames
        assert "unchanged.md" in filenames
        mock_archive.assert_not_called()


# ---------------------------------------------------------------------------
# Deploy subcommand — locking
# ---------------------------------------------------------------------------


class TestDeployLocking:
    """Test deploy lock acquisition and release."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_error_exits_with_code_1(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """LockError during acquire exits with code 1."""
        from ccfm_convert.state import LockError

        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock.acquire.side_effect = LockError("State is locked")
        mock_lock_class.return_value = mock_lock

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_deploy_argv(test_file)):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_released_even_on_deploy_error(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Lock is released in finally block even when deploy raises."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.side_effect = RuntimeError("deploy failed")

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with pytest.raises(RuntimeError):
            with patch("sys.argv", _base_deploy_argv(test_file)):
                main.main()

        mock_lock.release.assert_called_once()

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_lock_id_passed_to_acquire(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--lock-id is forwarded to lock_mgr.acquire."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch(
            "sys.argv",
            _base_deploy_argv(
                test_file,
                extra=["--lock-id", "ci-run-42"],
            ),
        ):
            main.main()

        mock_lock.acquire.assert_called_once_with(operation="deploy", lock_id="ci-run-42")


# ---------------------------------------------------------------------------
# Deploy subcommand — management page not found
# ---------------------------------------------------------------------------


class TestManagementPageDiscovery:
    """Test _find_management_page discovery."""

    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_find_management_page_exits_when_container_missing(self, mock_api_class, tmp_path):
        """_find_management_page exits 1 when _ccfm container page is not found."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api.find_page_by_title.return_value = None  # container not found
        mock_api_class.return_value = mock_api

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_deploy_argv(test_file)):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_find_management_page_exits_when_child_missing(self, mock_api_class, tmp_path):
        """_find_management_page exits 1 when container exists but management page child missing."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api.find_page_by_title.return_value = "container-id"
        mock_api.find_child_page_by_title.return_value = None  # management page not found
        mock_api_class.return_value = mock_api

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", _base_deploy_argv(test_file)):
                main.main()

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_find_management_page_returns_page_id(
        self,
        mock_api_class,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """_find_management_page returns page_id when container->child lookup succeeds."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api.find_page_by_title.return_value = "container-id"
        mock_api.find_child_page_by_title.return_value = "found-mgmt-id"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_file)):
            main.main()

        # ConfluenceBackend should have been called with the found mgmt page id
        mock_backend_class.assert_called_once_with(mock_api, "found-mgmt-id")


# ---------------------------------------------------------------------------
# Deploy subcommand — output
# ---------------------------------------------------------------------------


class TestDeployOutput:
    """Test deploy CLI output messages."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    @patch("sys.stdout", new_callable=StringIO)
    def test_success_output(
        self,
        mock_stdout,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Success message output includes 'Deployment complete'."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_file)):
            main.main()

        output = mock_stdout.getvalue()
        assert "Deployment complete" in output

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    @patch("sys.stdout", new_callable=StringIO)
    def test_space_id_printed(
        self,
        mock_stdout,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Space ID is printed during deployment."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_file)):
            main.main()

        output = mock_stdout.getvalue()
        assert "Space ID: space123" in output


# ---------------------------------------------------------------------------
# Deploy subcommand — error handling
# ---------------------------------------------------------------------------


class TestDeployErrorHandling:
    """Test error handling during deployment."""

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
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.side_effect = ValueError("Space not found")
        mock_api_class.return_value = mock_api

        with pytest.raises(ValueError):
            with patch("sys.argv", _base_deploy_argv(test_file)):
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

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_config_file_loaded_when_ccfm_yaml_present(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """ccfm.yaml is auto-loaded if present."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        config_file = tmp_path / "ccfm.yaml"
        config_file.write_text(
            "version: 1\ndomain: config.atlassian.net\nemail: cfg@example.com\nspace: CFG\n"
        )

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

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
                    "deploy",
                    "--file",
                    str(test_file),
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
                        "deploy",
                        "--file",
                        "test.md",
                    ],
                ):
                    main.main()
        finally:
            os.chdir(original)

        assert exc_info.value.code == 1

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_explicit_config_flag_loads_named_file(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """--config <path> loads the specified file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(
            "version: 1\ndomain: custom.atlassian.net\nemail: custom@example.com\nspace: CUS\n"
        )

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

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
                "deploy",
                "--file",
                str(test_file),
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
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_token_from_env_var(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Token is read from CONFLUENCE_TOKEN env var when --token is not provided."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

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
                    "deploy",
                    "--file",
                    str(test_file),
                ],
            ):
                main.main()

        mock_api_class.assert_called_once_with(
            "example.atlassian.net", "test@example.com", "env-token-value"
        )

    def test_missing_token_exits_with_error(self):
        """No --token and empty CONFLUENCE_TOKEN env var causes a SystemExit."""
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": ""}):
            with pytest.raises(SystemExit):
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
                        "deploy",
                        "--file",
                        "test.md",
                    ],
                ):
                    main.main()


# ---------------------------------------------------------------------------
# Path handling
# ---------------------------------------------------------------------------


class TestPathHandling:
    """Test path handling for file arguments."""

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_relative_path(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Relative path is accepted for --file."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            test_file = Path("test.md")
            test_file.write_text("# Test")

            mock_api = Mock()
            mock_api.get_space_id.return_value = "space123"
            mock_api_class.return_value = mock_api
            mock_hierarchy.return_value = (None, [])
            mock_deploy.return_value = None

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
                    "deploy",
                    "--file",
                    "test.md",
                ],
            ):
                main.main()

            mock_deploy.assert_called_once()
        finally:
            os.chdir(original_cwd)

    @patch("ccfm_convert.main.LockManager")
    @patch("ccfm_convert.main.StateManager")
    @patch("ccfm_convert.main.ConfluenceBackend")
    @patch("ccfm_convert.main.deploy_page")
    @patch("ccfm_convert.main.ensure_page_hierarchy")
    @patch("ccfm_convert.main._find_management_page", return_value="mgmt-page-id")
    @patch("ccfm_convert.main.ConfluenceAPI")
    def test_absolute_path(
        self,
        mock_api_class,
        mock_find_mgmt,
        mock_hierarchy,
        mock_deploy,
        mock_backend_class,
        mock_state_class,
        mock_lock_class,
        tmp_path,
    ):
        """Absolute path is accepted for --file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = (None, [])
        mock_deploy.return_value = None

        mock_state = Mock()
        mock_state_class.return_value = mock_state
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock

        with patch("sys.argv", _base_deploy_argv(test_file.absolute())):
            main.main()

        mock_deploy.assert_called_once()
