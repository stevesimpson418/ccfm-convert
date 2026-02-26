"""Tests for main.py CLI module."""

import os
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import main


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
