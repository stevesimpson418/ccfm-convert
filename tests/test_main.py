"""Tests for main.py CLI module."""

import os
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import main
from main import _derive_title, _rel_path


@pytest.fixture
def mock_api():
    """Create mock API."""
    api = Mock()
    api.get_space_id = Mock(return_value="space123")
    api.create_page = Mock(return_value="page123")
    api.update_page = Mock()
    api.add_labels = Mock()
    return api


class TestCLIArguments:
    """Test CLI argument parsing."""

    def test_required_arguments(self):
        """Test that required arguments are enforced."""
        with pytest.raises(SystemExit):
            with patch("sys.argv", ["main.py"]):
                main.main()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_single_file_deployment(self, mock_deploy, mock_api_class, tmp_path):
        """Test deploying single file."""
        # Create test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

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
                "--file",
                str(test_file),
            ],
        ):
            main.main()

        mock_deploy.assert_called_once()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_directory_deployment(self, mock_deploy_tree, mock_api_class, tmp_path):
        """Test deploying directory."""
        # Create test directory
        test_dir = tmp_path / "docs"
        test_dir.mkdir()

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

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
                "--directory",
                str(test_dir),
            ],
        ):
            main.main()

        mock_deploy_tree.assert_called_once()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_dump_mode(self, mock_deploy, mock_api_class, tmp_path):
        """Test dump mode (no actual deployment)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api_class.return_value = mock_api

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
                "--file",
                str(test_file),
                "--dump",
            ],
        ):
            main.main()

        # Should not call get_space_id in dump mode
        mock_api.get_space_id.assert_not_called()
        # Should still call deploy_page with dump=True
        mock_deploy.assert_called_once()
        assert mock_deploy.call_args[1]["dump"] is True

    @patch("main.ConfluenceAPI")
    def test_no_file_or_directory(self, mock_api_class):
        """Test error when neither file nor directory specified."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

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
                ],
            ):
                main.main()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_custom_docs_root(self, mock_deploy, mock_api_class, tmp_path):
        """Test custom docs root."""
        custom_root = tmp_path / "custom_docs"
        custom_root.mkdir()

        test_file = custom_root / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

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
                "--docs-root",
                str(custom_root),
                "--file",
                str(test_file),
            ],
        ):
            main.main()

        mock_deploy.assert_called_once()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_with_git_repo_url(self, mock_deploy, mock_api_class, tmp_path):
        """Test with git repo URL."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

        git_url = "https://github.com/user/repo"

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
                "--file",
                str(test_file),
                "--git-repo-url",
                git_url,
            ],
        ):
            main.main()

        # Should pass git URL to deploy_page
        call_args = mock_deploy.call_args[0]
        assert call_args[4] == git_url


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    @patch("main.ConfluenceAPI")
    @patch("main.ensure_page_hierarchy")
    @patch("main.deploy_page")
    def test_file_with_hierarchy(self, mock_deploy, mock_hierarchy, mock_api_class, tmp_path):
        """Test file deployment with automatic hierarchy."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        test_file = subdir / "page.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = "parent123"
        mock_deploy.return_value = None

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
                "--docs-root",
                str(docs_root),
                "--file",
                str(test_file),
            ],
        ):
            main.main()

        # Should create hierarchy
        mock_hierarchy.assert_called_once()
        # Should pass parent_id to deploy_page
        assert mock_deploy.call_args[0][2] == "parent123"

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_tree_deployment_with_git_url(self, mock_tree, mock_api_class, tmp_path):
        """Test tree deployment with git URL."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api

        git_url = "https://github.com/user/repo"

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
                "--directory",
                str(test_dir),
                "--git-repo-url",
                git_url,
            ],
        ):
            main.main()

        # Should pass git URL to deploy_tree
        call_args = mock_tree.call_args[0]
        assert call_args[4] == git_url


class TestErrorHandling:
    """Test error handling in CLI."""

    @patch("main.ConfluenceAPI")
    def test_invalid_space(self, mock_api_class):
        """Test handling of invalid space."""
        mock_api = Mock()
        mock_api.get_space_id.side_effect = ValueError("Space not found")
        mock_api_class.return_value = mock_api

        with pytest.raises(ValueError):
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
                    "INVALID",
                    "--file",
                    "test.md",
                ],
            ):
                main.main()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_nonexistent_file(self, mock_deploy, mock_api_class):
        """Test handling of non-existent file."""
        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
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
                    "--file",
                    "nonexistent.md",
                ],
            ):
                main.main()

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_api_error(self, mock_deploy, mock_api_class):
        """Test handling of API errors."""
        mock_api = Mock()
        mock_api.get_space_id.side_effect = RuntimeError("API Error")
        mock_api_class.return_value = mock_api

        with pytest.raises(RuntimeError):
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
                    "--file",
                    "test.md",
                ],
            ):
                main.main()


class TestOutput:
    """Test CLI output."""

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    @patch("sys.stdout", new_callable=StringIO)
    def test_success_output(self, mock_stdout, mock_deploy, mock_api_class, tmp_path):
        """Test success message output."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

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
                "--file",
                str(test_file),
            ],
        ):
            main.main()

        output = mock_stdout.getvalue()
        assert "Deployment complete" in output

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    @patch("sys.stdout", new_callable=StringIO)
    def test_dump_mode_output(self, mock_stdout, mock_deploy, mock_api_class, tmp_path):
        """Test dump mode output."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api_class.return_value = mock_api

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
                "--file",
                str(test_file),
                "--dump",
            ],
        ):
            main.main()

        output = mock_stdout.getvalue()
        assert "Dump mode" in output
        assert "Deployment complete" not in output


class TestPathHandling:
    """Test path handling."""

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_relative_path(self, mock_deploy, mock_api_class, tmp_path):
        """Test with relative path."""
        # Change to temp directory
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            test_file = Path("test.md")
            test_file.write_text("# Test")

            mock_api = Mock()
            mock_api.get_space_id.return_value = "space123"
            mock_api_class.return_value = mock_api
            mock_deploy.return_value = None

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
                    "--file",
                    "test.md",
                ],
            ):
                main.main()

            mock_deploy.assert_called_once()
        finally:
            os.chdir(original_cwd)

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_absolute_path(self, mock_deploy, mock_api_class, tmp_path):
        """Test with absolute path."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

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
                "--file",
                str(test_file.absolute()),
            ],
        ):
            main.main()

        mock_deploy.assert_called_once()


class TestTokenHandling:
    """Test API token supplied via CLI arg or CONFLUENCE_TOKEN env var."""

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_token_from_env_var(self, mock_deploy, mock_api_class, tmp_path):
        """Token is read from CONFLUENCE_TOKEN env var when --token is not provided."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

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
                        "--file",
                        "test.md",
                    ],
                ):
                    main.main()


# ---------------------------------------------------------------------------
# _rel_path helper (lines 14-19)
# ---------------------------------------------------------------------------


class TestRelPath:
    def test_rel_path_returns_relative_string_when_under_cwd(self, tmp_path):
        """Returns relative path string when filepath is under cwd (line 17)."""
        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            f = tmp_path / "docs" / "page.md"
            result = _rel_path(f)
            assert result == "docs/page.md"
        finally:
            os.chdir(original)

    def test_rel_path_returns_absolute_string_when_outside_cwd(self):
        """Returns absolute path string when filepath is not under cwd (lines 18-19)."""
        # Use an absolute path definitely not under cwd
        f = Path("/some/absolute/path/file.md")
        result = _rel_path(f)
        assert result == "/some/absolute/path/file.md"


# ---------------------------------------------------------------------------
# _derive_title helper
# ---------------------------------------------------------------------------


class TestDeriveTitle:
    def test_returns_frontmatter_title(self, tmp_path):
        """Returns frontmatter title when page_meta.title is present (line 29)."""
        f = tmp_path / "my-page.md"
        f.write_text("---\npage_meta:\n  title: Custom Title\n---\n# Content")
        assert _derive_title(f) == "Custom Title"

    def test_falls_back_to_stem_when_no_frontmatter(self, tmp_path):
        """Returns stem-derived title when frontmatter has no title."""
        f = tmp_path / "my-page.md"
        f.write_text("# Content without frontmatter")
        assert _derive_title(f) == "My Page"

    def test_falls_back_to_stem_on_read_error(self, tmp_path):
        """Returns stem-derived title when file cannot be read (lines 30-31)."""
        f = tmp_path / "unreadable-doc.md"
        # Don't create the file — read_text will raise OSError
        assert _derive_title(f) == "Unreadable Doc"


# ---------------------------------------------------------------------------
# Config file loading (lines 97-104)
# ---------------------------------------------------------------------------


class TestConfigFileLoading:
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_config_file_loaded_when_ccfm_yaml_present(self, mock_deploy, mock_api_class, tmp_path):
        """ccfm.yaml is auto-loaded if present (lines 98-104)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        config_file = tmp_path / "ccfm.yaml"
        config_file.write_text(
            "version: 1\ndomain: config.atlassian.net\nemail: cfg@example.com\nspace: CFG\n"
        )

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch(
                "sys.argv",
                ["main.py", "--token", "tok", "--file", str(test_file)],
            ):
                main.main()
        finally:
            os.chdir(original)

        # domain was supplied by config file, not CLI
        mock_api_class.assert_called_once_with("config.atlassian.net", "cfg@example.com", "tok")

    @patch("main.load_config")
    def test_config_file_load_error_exits_with_code_1(self, mock_load_config, tmp_path):
        """Bad config file causes sys.exit(1) (lines 99-104)."""
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
                        "--file",
                        "test.md",
                        "--config",
                        str(config_file),
                    ],
                ):
                    main.main()
        finally:
            os.chdir(original)

        assert exc_info.value.code == 1

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    def test_explicit_config_flag_loads_named_file(self, mock_deploy, mock_api_class, tmp_path):
        """--config <path> loads the specified file, not the default ccfm.yaml (lines 97-104)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(
            "version: 1\ndomain: custom.atlassian.net\nemail: custom@example.com\nspace: CUS\n"
        )

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy.return_value = None

        with patch(
            "sys.argv",
            [
                "main.py",
                "--token",
                "tok",
                "--config",
                str(custom_config),
                "--file",
                str(test_file),
            ],
        ):
            main.main()

        mock_api_class.assert_called_once_with("custom.atlassian.net", "custom@example.com", "tok")


# ---------------------------------------------------------------------------
# --plan mode (lines 147-154)
# ---------------------------------------------------------------------------


class TestPlanMode:
    @patch("main.compute_plan")
    def test_plan_mode_no_changes_exits_zero(self, mock_compute_plan, tmp_path):
        """--plan exits 0 when there are no pending changes."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_plan = Mock()
        mock_plan.has_changes.return_value = False
        mock_compute_plan.return_value = mock_plan

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
                    "tok",
                    "--space",
                    "TEST",
                    "--plan",
                    "--file",
                    str(test_file),
                ],
            ):
                main.main()

        assert exc_info.value.code == 0
        mock_compute_plan.assert_called_once()
        mock_plan.print_summary.assert_called_once()

    @patch("main.compute_plan")
    def test_plan_mode_has_changes_exits_two(self, mock_compute_plan, tmp_path):
        """--plan exits 2 when there are pending changes (CI-detectable)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_plan = Mock()
        mock_plan.has_changes.return_value = True
        mock_compute_plan.return_value = mock_plan

        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--plan",
                    "--file",
                    str(test_file),
                ],
            ):
                main.main()

        assert exc_info.value.code == 2

    @patch("main.compute_plan")
    def test_plan_mode_with_archive_orphans(self, mock_compute_plan, tmp_path):
        """--plan --archive-orphans passes archive_orphans=True to compute_plan."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_compute_plan.return_value = Mock()

        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--plan",
                    "--archive-orphans",
                    "--file",
                    str(test_file),
                ],
            ):
                main.main()

        call_kwargs = mock_compute_plan.call_args[1]
        assert call_kwargs["archive_orphans"] is True

    @patch("main.compute_plan")
    def test_plan_mode_with_directory(self, mock_compute_plan, tmp_path):
        """--plan with --directory collects md files for the plan."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# A")
        (docs / ".page_content.md").write_text("# Container")

        mock_compute_plan.return_value = Mock()

        with pytest.raises(SystemExit):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--plan",
                    "--directory",
                    str(docs),
                ],
            ):
                main.main()

        # .page_content.md excluded; only a.md in target_files
        call_kwargs = mock_compute_plan.call_args[1]
        files = call_kwargs["files"]
        assert all(f.name != ".page_content.md" for f in files)


# ---------------------------------------------------------------------------
# --changed-only (lines 160-165)
# ---------------------------------------------------------------------------


class TestChangedOnlyMode:
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_changed_only_prints_count_message(
        self, mock_deploy_tree, mock_api_class, tmp_path, capsys
    ):
        """--changed-only prints the count of changed files (lines 160-165)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        changed = docs / "changed.md"
        unchanged = docs / "unchanged.md"
        changed.write_text("# New Content")
        unchanged.write_text("# Old Content")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = []

        # Pre-populate state so 'unchanged.md' already matches its hash
        from state.manager import StateManager

        state_file = tmp_path / ".ccfm-state.json"
        sm = StateManager(state_file)

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            unchanged_rel = str(unchanged.relative_to(tmp_path))
            sm.set_page(unchanged_rel, "p1", "Unchanged", "TEST", "s1", sm.compute_hash(unchanged))
            sm.save()

            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "tok",
                    "--space",
                    "TEST",
                    "--directory",
                    str(docs),
                    "--changed-only",
                    "--state",
                    str(state_file),
                ],
            ):
                main.main()
        finally:
            os.chdir(original)

        captured = capsys.readouterr()
        # 'changed.md' has no state entry → has_changed=True; 'unchanged.md' matches → filtered out
        assert "--changed-only: 1 file(s) with changes" in captured.out


# ---------------------------------------------------------------------------
# --dump with directory (lines 174-175)
# ---------------------------------------------------------------------------


class TestDumpModeDirectory:
    @patch("main.deploy_tree")
    def test_dump_mode_directory_calls_deploy_tree_with_dump_true(self, mock_deploy_tree, tmp_path):
        """dump mode with --directory calls deploy_tree(dump=True) (lines 174-175)."""
        test_dir = tmp_path / "docs"
        test_dir.mkdir()

        with patch(
            "sys.argv",
            [
                "main.py",
                "--domain",
                "example.atlassian.net",
                "--email",
                "test@example.com",
                "--token",
                "tok",
                "--space",
                "TEST",
                "--directory",
                str(test_dir),
                "--dump",
            ],
        ):
            main.main()

        mock_deploy_tree.assert_called_once()
        call_kwargs = mock_deploy_tree.call_args[1]
        assert call_kwargs.get("dump") is True


# ---------------------------------------------------------------------------
# State save after file deploy (lines 192-200)
# ---------------------------------------------------------------------------


class TestStateSaveAfterFileDeploy:
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    @patch("main.ensure_page_hierarchy")
    def test_state_saved_after_successful_file_deploy(
        self, mock_hierarchy, mock_deploy, mock_api_class, tmp_path
    ):
        """state.set_page and state.save are called when deploy_page returns a page_id (lines 192-200)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = None
        mock_deploy.return_value = "deployed-page-id"

        state_file = tmp_path / ".ccfm-state.json"

        with patch(
            "sys.argv",
            [
                "main.py",
                "--domain",
                "example.atlassian.net",
                "--email",
                "test@example.com",
                "--token",
                "tok",
                "--space",
                "TEST",
                "--file",
                str(test_file),
                "--state",
                str(state_file),
            ],
        ):
            main.main()

        import json

        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert any(v["page_id"] == "deployed-page-id" for v in data["pages"].values())

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_page")
    @patch("main.ensure_page_hierarchy")
    def test_state_not_saved_when_deploy_returns_none(
        self, mock_hierarchy, mock_deploy, mock_api_class, tmp_path
    ):
        """state.save not called if deploy_page returns None (lines 191 condition)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_hierarchy.return_value = None
        mock_deploy.return_value = None  # skipped page

        state_file = tmp_path / ".ccfm-state.json"

        with patch(
            "sys.argv",
            [
                "main.py",
                "--domain",
                "example.atlassian.net",
                "--email",
                "test@example.com",
                "--token",
                "tok",
                "--space",
                "TEST",
                "--file",
                str(test_file),
                "--state",
                str(state_file),
            ],
        ):
            main.main()

        assert not state_file.exists()


# ---------------------------------------------------------------------------
# State save after tree deploy (lines 207-216)
# ---------------------------------------------------------------------------


class TestStateSaveAfterTreeDeploy:
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_state_saved_for_each_deployed_page_in_tree(
        self, mock_deploy_tree, mock_api_class, tmp_path
    ):
        """state.set_page is called per page_id returned from deploy_tree (lines 207-216)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f1 = docs / "page1.md"
        f2 = docs / "page2.md"
        f1.write_text("# P1")
        f2.write_text("# P2")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        # deploy_tree returns (filepath, page_id) tuples
        mock_deploy_tree.return_value = [(f1, "pid1"), (f2, "pid2")]

        state_file = tmp_path / ".ccfm-state.json"

        with patch(
            "sys.argv",
            [
                "main.py",
                "--domain",
                "example.atlassian.net",
                "--email",
                "test@example.com",
                "--token",
                "tok",
                "--space",
                "TEST",
                "--directory",
                str(docs),
                "--state",
                str(state_file),
            ],
        ):
            main.main()

        import json

        data = json.loads(state_file.read_text())
        page_ids = {v["page_id"] for v in data["pages"].values()}
        assert "pid1" in page_ids
        assert "pid2" in page_ids

    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_state_skips_none_page_ids_in_tree(self, mock_deploy_tree, mock_api_class, tmp_path):
        """page_id=None entries from deploy_tree are not written to state (line 207 condition)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f1 = docs / "deployed.md"
        f2 = docs / "skipped.md"
        f1.write_text("# D")
        f2.write_text("# S")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = [(f1, "pid-ok"), (f2, None)]

        state_file = tmp_path / ".ccfm-state.json"

        with patch(
            "sys.argv",
            [
                "main.py",
                "--domain",
                "example.atlassian.net",
                "--email",
                "test@example.com",
                "--token",
                "tok",
                "--space",
                "TEST",
                "--directory",
                str(docs),
                "--state",
                str(state_file),
            ],
        ):
            main.main()

        import json

        data = json.loads(state_file.read_text())
        page_ids = {v["page_id"] for v in data["pages"].values()}
        assert "pid-ok" in page_ids
        assert len(page_ids) == 1


# ---------------------------------------------------------------------------
# --archive-orphans live deploy (lines 222-233)
# ---------------------------------------------------------------------------


class TestArchiveOrphansLiveDeploy:
    @patch("main.archive_page")
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_archive_orphans_calls_archive_and_removes_from_state(
        self, mock_deploy_tree, mock_api_class, mock_archive, tmp_path
    ):
        """Orphaned pages are archived and removed from state (lines 222-231)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        active = docs / "active.md"
        active.write_text("# Active")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = [(active, "active-pid")]
        mock_archive.return_value = True

        state_file = tmp_path / ".ccfm-state.json"

        # Pre-populate state with a now-deleted page
        from state.manager import StateManager

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            sm = StateManager(state_file)
            sm.set_page("docs/deleted.md", "orphan-pid", "Deleted", "TEST", "s1", "sha256:x")
            sm.save()

            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "tok",
                    "--space",
                    "TEST",
                    "--directory",
                    str(docs),
                    "--archive-orphans",
                    "--state",
                    str(state_file),
                ],
            ):
                main.main()
        finally:
            os.chdir(original)

        mock_archive.assert_called_once_with(mock_api, "orphan-pid", "Deleted")

        import json

        data = json.loads(state_file.read_text())
        assert "docs/deleted.md" not in data["pages"]

    @patch("main.archive_page")
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_archive_orphans_no_orphans_prints_message(
        self, mock_deploy_tree, mock_api_class, mock_archive, tmp_path, capsys
    ):
        """When no orphans found, prints info message (lines 232-233)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        active = docs / "active.md"
        active.write_text("# Active")

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = [(active, "active-pid")]

        state_file = tmp_path / ".ccfm-state.json"

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "tok",
                    "--space",
                    "TEST",
                    "--directory",
                    str(docs),
                    "--archive-orphans",
                    "--state",
                    str(state_file),
                ],
            ):
                main.main()
        finally:
            os.chdir(original)

        captured = capsys.readouterr()
        assert "No orphaned pages found" in captured.out
        mock_archive.assert_not_called()

    @patch("main.archive_page")
    @patch("main.ConfluenceAPI")
    @patch("main.deploy_tree")
    def test_archive_failure_does_not_remove_from_state(
        self, mock_deploy_tree, mock_api_class, mock_archive, tmp_path
    ):
        """If archive_page returns False, entry stays in state (line 229 condition)."""
        docs = tmp_path / "docs"
        docs.mkdir()

        mock_api = Mock()
        mock_api.get_space_id.return_value = "space123"
        mock_api_class.return_value = mock_api
        mock_deploy_tree.return_value = []
        mock_archive.return_value = False  # simulate archive failure

        state_file = tmp_path / ".ccfm-state.json"

        from state.manager import StateManager

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            sm = StateManager(state_file)
            sm.set_page("docs/orphan.md", "orphan-id", "Orphan", "TEST", "s1", "sha256:x")
            sm.save()

            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--domain",
                    "example.atlassian.net",
                    "--email",
                    "test@example.com",
                    "--token",
                    "tok",
                    "--space",
                    "TEST",
                    "--directory",
                    str(docs),
                    "--archive-orphans",
                    "--state",
                    str(state_file),
                ],
            ):
                main.main()
        finally:
            os.chdir(original)

        import json

        data = json.loads(state_file.read_text())
        # Entry should still be present since archive failed
        assert "docs/orphan.md" in data["pages"]
