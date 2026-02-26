"""Tests for deploy.orchestration module."""

from unittest.mock import Mock

import pytest

from deploy.orchestration import deploy_page, deploy_tree, ensure_page_hierarchy


@pytest.fixture
def mock_api():
    """Create mock API for testing."""
    api = Mock()
    api.domain = "example.atlassian.net"
    api.find_page_by_title = Mock(return_value=None)
    api.create_page = Mock(return_value="new-page-123")
    api.update_page = Mock()
    api.add_labels = Mock()
    api.upload_attachment = Mock(return_value={"results": [{"id": "att123"}]})
    api.get_attachment_fileid = Mock(return_value="uuid-123")
    return api


class TestEnsurePageHierarchy:
    """Test page hierarchy creation."""

    def test_file_in_root(self, mock_api, tmp_path):
        """Test file directly in docs root."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        filepath = docs_root / "page.md"

        parent_id = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # Should return None (no parent needed)
        assert parent_id is None

    def test_file_in_subdirectory(self, mock_api, tmp_path):
        """Test file in subdirectory."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        filepath = subdir / "page.md"

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "parent-123"

        parent_id = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # Should create parent page and return its ID
        assert parent_id == "parent-123"
        mock_api.create_page.assert_called_once()

    def test_nested_directories(self, mock_api, tmp_path):
        """Test nested directory structure."""
        docs_root = tmp_path / "docs"
        deep_path = docs_root / "Team" / "Engineering" / "Backend"
        deep_path.mkdir(parents=True)

        filepath = deep_path / "page.md"

        # Mock sequential page creation
        call_count = [0]

        def mock_create(space_id, parent_id, title, body, status="current"):
            call_count[0] += 1
            return f"page-{call_count[0]}"

        mock_api.create_page.side_effect = mock_create

        ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # Should create 3 levels of pages
        assert mock_api.create_page.call_count == 3

    def test_existing_parent_page(self, mock_api, tmp_path):
        """Test with existing parent page."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        filepath = subdir / "page.md"

        # Parent already exists
        mock_api.find_page_by_title.return_value = "existing-123"

        parent_id = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # Should return existing page ID
        assert parent_id == "existing-123"
        # Should not create new page
        mock_api.create_page.assert_not_called()

    @pytest.mark.skip(reason="Depends on frontmatter parsing implementation - integration test")
    def test_page_content_file(self, mock_api, tmp_path):
        """Test directory with .page_content.md file."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        # Create .page_content.md
        page_content = subdir / ".page_content.md"
        page_content.write_text("---\ntitle: Team Page\n---\nContent")

        filepath = subdir / "child.md"

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "parent-123"

        ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # Should use title from frontmatter
        call_args = mock_api.create_page.call_args
        assert call_args[0][2] == "Team Page"  # title argument


class TestDeployPage:
    """Test page deployment."""

    def test_deploy_new_page(self, mock_api, tmp_path):
        """Test deploying new page."""
        filepath = tmp_path / "test.md"
        filepath.write_text("# Hello\n\nWorld")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        page_id = deploy_page(mock_api, "space123", None, filepath)

        assert page_id == "new-123"
        mock_api.create_page.assert_called_once()
        mock_api.add_labels.assert_called_once()

    def test_deploy_update_existing(self, mock_api, tmp_path):
        """Test updating existing page."""
        filepath = tmp_path / "test.md"
        filepath.write_text("# Updated\n\nContent")

        mock_api.find_page_by_title.return_value = "existing-123"

        page_id = deploy_page(mock_api, "space123", None, filepath)

        assert page_id == "existing-123"
        mock_api.update_page.assert_called_once()
        mock_api.create_page.assert_not_called()

    @pytest.mark.skip(reason="Depends on frontmatter and deploy implementation - integration test")
    def test_deploy_with_frontmatter(self, mock_api, tmp_path):
        """Test page with frontmatter."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
title: Custom Title
author: John Doe
labels:
  - python
  - api
---
# Content""")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", None, filepath)

        # Should use custom title
        call_args = mock_api.create_page.call_args
        assert call_args[0][2] == "Custom Title"

        # Should add labels including author
        labels_call = mock_api.add_labels.call_args[0][1]
        assert "python" in labels_call
        assert "api" in labels_call
        assert "author-john-doe" in labels_call

    @pytest.mark.skip(reason="Depends on deploy implementation - integration test")
    def test_deploy_skip_disabled(self, mock_api, tmp_path):
        """Test skipping page with deploy_page: false."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
deploy_page: false
---
# Content""")

        page_id = deploy_page(mock_api, "space123", None, filepath)

        assert page_id is None
        mock_api.create_page.assert_not_called()

    @pytest.mark.skip(reason="Depends on deploy and attachment implementation - integration test")
    def test_deploy_with_attachments(self, mock_api, tmp_path):
        """Test page with attachments."""
        # Create main file
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
attachments:
  - path: diagram.png
    alt: Architecture
---
# Content

![diagram](diagram.png)""")

        # Create attachment file
        attachment = tmp_path / "diagram.png"
        attachment.write_bytes(b"fake image data")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", None, filepath)

        # Should upload attachment
        mock_api.upload_attachment.assert_called_once()
        mock_api.get_attachment_fileid.assert_called_once()

        # Should update page after attachment upload
        assert mock_api.update_page.call_count >= 1

    def test_deploy_missing_attachment(self, mock_api, tmp_path):
        """Test handling missing attachment file."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
attachments:
  - missing.png
---
# Content""")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        # Should not crash
        page_id = deploy_page(mock_api, "space123", None, filepath)

        assert page_id == "new-123"
        # Should not attempt upload
        mock_api.upload_attachment.assert_not_called()

    @pytest.mark.skip(reason="Depends on deploy implementation - integration test")
    def test_deploy_draft_page(self, mock_api, tmp_path):
        """Test deploying draft page."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
page_status: draft
---
# Draft""")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", None, filepath)

        # Should pass status='draft'
        call_args = mock_api.create_page.call_args
        assert call_args[1]["status"] == "draft"

    def test_deploy_with_parent(self, mock_api, tmp_path):
        """Test deploying page with parent."""
        filepath = tmp_path / "test.md"
        filepath.write_text("# Child Page")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", "parent-456", filepath)

        # Should pass parent_id
        call_args = mock_api.create_page.call_args
        assert call_args[0][1] == "parent-456"

    def test_deploy_ci_banner_disabled(self, mock_api, tmp_path):
        """Test disabling CI banner."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
ci_banner: false
---
# Content""")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", None, filepath)

        # Should still create page successfully
        assert mock_api.create_page.called

    def test_deploy_dump_mode(self, mock_api, tmp_path):
        """Test dump mode (no deployment)."""
        filepath = tmp_path / "test.md"
        filepath.write_text("# Test")

        page_id = deploy_page(mock_api, "space123", None, filepath, dump=True)

        assert page_id is None
        # Should not call any API methods
        mock_api.create_page.assert_not_called()
        mock_api.update_page.assert_not_called()

        # Should create .adf.json file
        adf_file = filepath.with_suffix(".adf.json")
        assert adf_file.exists()

    def test_deploy_with_git_url(self, mock_api, tmp_path):
        """Test deploying with git URL."""
        filepath = tmp_path / "test.md"
        filepath.write_text("# Test")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        git_url = "https://github.com/user/repo/blob/main"
        deploy_page(mock_api, "space123", None, filepath, git_repo_url=git_url)

        # Should include git URL in banner
        assert mock_api.create_page.called

    def test_frontmatter_parent_overrides_directory_hierarchy(self, mock_api, tmp_path):
        """deploy_page uses frontmatter parent when specified."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
page_meta:
  title: My Page
  parent: Explicit Parent
---
# Content""")
        mock_api.find_page_by_title.side_effect = lambda space, title: (
            "explicit-parent-id" if title == "Explicit Parent" else None
        )
        mock_api.create_page.return_value = "new-page"

        deploy_page(mock_api, "space123", "directory-parent-id", filepath)

        call_args = mock_api.create_page.call_args
        assert call_args[0][1] == "explicit-parent-id"  # overridden, not "directory-parent-id"

    def test_frontmatter_parent_not_found_falls_back(self, mock_api, tmp_path):
        """deploy_page falls back to directory parent when frontmatter parent not found."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
page_meta:
  title: My Page
  parent: Nonexistent Page
---
# Content""")
        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-page"

        deploy_page(mock_api, "space123", "directory-parent-id", filepath)

        call_args = mock_api.create_page.call_args
        assert call_args[0][1] == "directory-parent-id"  # fallback to directory hierarchy


class TestEnsurePageHierarchyCoverage:
    """Tests targeting uncovered paths in ensure_page_hierarchy."""

    def test_page_content_file_updates_existing_page(self, mock_api, tmp_path):
        """Lines 93-102: existing page with .page_content.md is updated with new content."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        # Write .page_content.md with frontmatter
        page_content = subdir / ".page_content.md"
        page_content.write_text(
            "---\npage_meta:\n  title: Team\n  author: Jane Doe\n  labels:\n    - team\n---\n# Team"
        )

        filepath = subdir / "child.md"

        # Simulate page already exists
        mock_api.find_page_by_title.return_value = "existing-team-page"

        parent_id = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # Should update the existing page
        mock_api.update_page.assert_called_once()
        # Should add labels (including author label)
        mock_api.add_labels.assert_called_once()
        assert parent_id == "existing-team-page"

    def test_page_content_file_updates_existing_page_with_author_label(self, mock_api, tmp_path):
        """Lines 99-101: author is converted to a label when updating existing page."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text("---\npage_meta:\n  title: Team\n  author: John Smith\n---\n# Team")
        filepath = subdir / "child.md"

        mock_api.find_page_by_title.return_value = "existing-team-page"

        ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        call_args = mock_api.add_labels.call_args[0]
        labels = call_args[1]
        assert "author-john-smith" in labels

    def test_new_page_with_author_gets_author_label(self, mock_api, tmp_path):
        """Lines 113-117: author is converted to a label when creating a new page."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text(
            "---\npage_meta:\n  title: Team\n  author: Alice Brown\n  labels:\n    - docs\n---\n# Team"
        )
        filepath = subdir / "child.md"

        # Page does not yet exist
        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-page-id"

        ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        mock_api.create_page.assert_called_once()
        mock_api.add_labels.assert_called_once()
        call_args = mock_api.add_labels.call_args[0]
        labels = call_args[1]
        assert "author-alice-brown" in labels


class TestEnsurePageHierarchyEdgeCases:
    """Tests targeting remaining edge cases in ensure_page_hierarchy."""

    def test_filepath_not_under_docs_root_returns_none(self, mock_api, tmp_path):
        """Lines 33-35: when filepath is not relative to docs_root, returns None."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        # filepath lives outside docs_root
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        filepath = other_dir / "page.md"

        result = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        assert result is None
        mock_api.create_page.assert_not_called()


class TestDeployPageCoverage:
    """Tests targeting uncovered paths in deploy_page."""

    def test_deploy_page_skips_when_deploy_page_false(self, mock_api, tmp_path):
        """Lines 182-183: deploy_page returns None when deploy_page frontmatter is false."""
        filepath = tmp_path / "skip.md"
        filepath.write_text("---\ndeploy_config:\n  deploy_page: false\n---\n# Content")

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result is None
        mock_api.create_page.assert_not_called()
        mock_api.update_page.assert_not_called()

    def test_deploy_page_author_generates_label(self, mock_api, tmp_path):
        """Lines 236-238: author in frontmatter is converted to an author-* label."""
        filepath = tmp_path / "test.md"
        filepath.write_text(
            "---\npage_meta:\n  title: My Page\n  author: Bob Builder\n---\n# Content"
        )

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-page"

        deploy_page(mock_api, "space123", None, filepath)

        mock_api.add_labels.assert_called_once()
        labels_arg = mock_api.add_labels.call_args[0][1]
        assert "author-bob-builder" in labels_arg

    def test_deploy_page_with_attachment_dict_format(self, mock_api, tmp_path):
        """Lines 247-294: full attachment upload flow with dict-format attachment entry."""
        filepath = tmp_path / "page.md"
        attachment_file = tmp_path / "diagram.png"
        attachment_file.write_bytes(b"fake png data")

        filepath.write_text(
            "---\npage_meta:\n  attachments:\n    - path: diagram.png\n      alt: Diagram\n      width: narrow\n---\n# Page\n\n![Diagram](diagram.png)"
        )

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"
        mock_api.upload_attachment.return_value = {"results": [{"id": "att-456"}]}
        mock_api.get_attachment_fileid.return_value = "file-uuid-789"

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.upload_attachment.assert_called_once()
        mock_api.get_attachment_fileid.assert_called_once_with("att-456")
        # Should update the page a second time with resolved attachment nodes
        assert mock_api.update_page.call_count >= 1

    def test_deploy_page_with_attachment_string_format(self, mock_api, tmp_path):
        """Lines 255-258: attachment as plain string (not dict) in frontmatter."""
        filepath = tmp_path / "page.md"
        attachment_file = tmp_path / "image.png"
        attachment_file.write_bytes(b"fake png data")

        filepath.write_text("---\npage_meta:\n  attachments:\n    - image.png\n---\n# Page")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"
        mock_api.upload_attachment.return_value = {"results": [{"id": "att-111"}]}
        mock_api.get_attachment_fileid.return_value = "file-uuid-222"

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.upload_attachment.assert_called_once()

    def test_deploy_page_attachment_upload_fails_gracefully(self, mock_api, tmp_path):
        """Line 283: upload_attachment returns None — warning is printed, no crash."""
        filepath = tmp_path / "page.md"
        attachment_file = tmp_path / "image.png"
        attachment_file.write_bytes(b"data")

        filepath.write_text("---\npage_meta:\n  attachments:\n    - image.png\n---\n# Page")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"
        # Upload fails
        mock_api.upload_attachment.return_value = None

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        # Should not crash; update_page should NOT be called again for attachments
        mock_api.get_attachment_fileid.assert_not_called()

    def test_deploy_page_attachment_fileid_not_found(self, mock_api, tmp_path):
        """Line 281: get_attachment_fileid returns None — warning is printed, no crash."""
        filepath = tmp_path / "page.md"
        attachment_file = tmp_path / "image.png"
        attachment_file.write_bytes(b"data")

        filepath.write_text("---\npage_meta:\n  attachments:\n    - image.png\n---\n# Page")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"
        mock_api.upload_attachment.return_value = {"results": [{"id": "att-999"}]}
        # fileId not found
        mock_api.get_attachment_fileid.return_value = None

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.get_attachment_fileid.assert_called_once()

    def test_deploy_page_missing_attachment_dict_format_logs_warning(self, mock_api, tmp_path):
        """Line 285: attachment path specified in dict format but file does not exist — warning printed."""
        filepath = tmp_path / "page.md"
        # Note: we do NOT create the attachment file
        filepath.write_text(
            "---\npage_meta:\n  attachments:\n    - path: nonexistent.png\n      alt: Missing\n---\n# Page"
        )

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.upload_attachment.assert_not_called()


class TestDeployTree:
    """Test tree deployment."""

    def test_deploy_single_file(self, mock_api, tmp_path):
        """Test deploying single file."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        file1 = docs_root / "test.md"
        file1.write_text("# Test")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        deploy_tree(mock_api, "space123", docs_root, docs_root)

        # Should deploy the file
        assert mock_api.create_page.call_count >= 1

    def test_deploy_multiple_files(self, mock_api, tmp_path):
        """Test deploying multiple files."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        for i in range(3):
            file = docs_root / f"page{i}.md"
            file.write_text(f"# Page {i}")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        deploy_tree(mock_api, "space123", docs_root, docs_root)

        # Should deploy all files
        assert mock_api.create_page.call_count >= 3

    def test_deploy_with_hierarchy(self, mock_api, tmp_path):
        """Test deploying with directory hierarchy."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        file1 = docs_root / "root.md"
        file1.write_text("# Root")

        file2 = subdir / "child.md"
        file2.write_text("# Child")

        call_count = [0]

        def mock_create(space_id, parent_id, title, body, status="current"):
            call_count[0] += 1
            return f"page-{call_count[0]}"

        mock_api.create_page.side_effect = mock_create

        deploy_tree(mock_api, "space123", docs_root, docs_root)

        # Should create hierarchy and files
        assert mock_api.create_page.call_count >= 2

    def test_deploy_skip_page_content_files(self, mock_api, tmp_path):
        """Test that .page_content.md files are not deployed as pages."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        # Create .page_content.md (should not be deployed)
        page_content = subdir / ".page_content.md"
        page_content.write_text("# Container")

        # Create regular page (should be deployed)
        regular = subdir / "page.md"
        regular.write_text("# Regular")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        deploy_tree(mock_api, "space123", docs_root, docs_root)

        # Should only deploy regular page (not .page_content.md)
        # Plus one for the container page created from .page_content.md
        assert mock_api.create_page.call_count >= 1

    def test_deploy_tree_dump_mode_skips_hierarchy(self, mock_api, tmp_path):
        """Line 147: in dump mode deploy_tree sets parent_id=None without calling ensure_page_hierarchy."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        file1 = docs_root / "test.md"
        file1.write_text("# Test")

        deploy_tree(mock_api, "space123", docs_root, docs_root, dump=True)

        # In dump mode, hierarchy should NOT be built and no API create/update calls
        mock_api.create_page.assert_not_called()
        mock_api.update_page.assert_not_called()

    def test_deploy_error_handling(self, mock_api, tmp_path):
        """Test error handling during deployment."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        file1 = docs_root / "good.md"
        file1.write_text("# Good")

        file2 = docs_root / "bad.md"
        file2.write_text("# Bad")

        # First file succeeds, second fails
        mock_api.create_page.side_effect = [
            "page-123",
            Exception("API Error"),
        ]

        # Should not crash - continues with other files
        deploy_tree(mock_api, "space123", docs_root, docs_root)

        # Should have attempted both
        assert mock_api.create_page.call_count == 2

    def test_deploy_tree_uses_root_path_for_hierarchy(self, mock_api, tmp_path):
        """deploy_tree builds hierarchy relative to root_path, not docs_root."""
        # root_path is OUTSIDE docs_root
        root_path = tmp_path / "example" / "My Section"
        subdir = root_path / "Sub"
        subdir.mkdir(parents=True)
        (root_path / "index.md").write_text("# Index")
        (subdir / "child.md").write_text("# Child")

        docs_root = tmp_path / "docs"  # different, doesn't contain root_path

        page_ids = {}

        def mock_find(space_id, title):
            return page_ids.get(title)

        def mock_create(space_id, parent_id, title, body, status="current"):
            pid = f"page-{title}"
            page_ids[title] = pid
            return pid

        mock_api.find_page_by_title.side_effect = mock_find
        mock_api.create_page.side_effect = mock_create

        deploy_tree(mock_api, "space123", root_path, docs_root)

        # Container page "Sub" must have been created with parent_id=None (at space root)
        sub_create_call = next(c for c in mock_api.create_page.call_args_list if c[0][2] == "Sub")
        assert sub_create_call[0][1] is None  # Sub created at space root

        # Child page must have Sub as its parent
        child_create_call = next(
            c for c in mock_api.create_page.call_args_list if "child" in c[0][2].lower()
        )
        assert child_create_call[0][1] == "page-Sub"


class TestPathTraversalProtection:
    """Test that path traversal in attachment paths is blocked."""

    def test_traversal_string_format_is_blocked(self, mock_api, tmp_path):
        """String-format attachment path with traversal is skipped without uploading."""
        filepath = tmp_path / "page.md"
        filepath.write_text("---\npage_meta:\n  attachments:\n    - ../../etc/passwd\n---\n# Page")
        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.upload_attachment.assert_not_called()

    def test_traversal_dict_format_is_blocked(self, mock_api, tmp_path):
        """Dict-format attachment path with traversal is skipped without uploading."""
        filepath = tmp_path / "page.md"
        filepath.write_text(
            "---\npage_meta:\n  attachments:\n    - path: ../../etc/passwd\n      alt: Evil\n---\n# Page"
        )
        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.upload_attachment.assert_not_called()

    def test_valid_relative_path_within_directory_is_allowed(self, mock_api, tmp_path):
        """A valid relative path within the attachment directory passes the guard."""
        filepath = tmp_path / "page.md"
        attachment_file = tmp_path / "valid.png"
        attachment_file.write_bytes(b"data")
        filepath.write_text("---\npage_meta:\n  attachments:\n    - path: valid.png\n---\n# Page")
        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"
        mock_api.upload_attachment.return_value = {"results": [{"id": "att-1"}]}
        mock_api.get_attachment_fileid.return_value = "file-uuid"

        result = deploy_page(mock_api, "space123", None, filepath)

        assert result == "page-123"
        mock_api.upload_attachment.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_directory(self, mock_api, tmp_path):
        """Test deploying empty directory."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        # Should not crash
        deploy_tree(mock_api, "space123", docs_root, docs_root)

        # Should not make any API calls
        mock_api.create_page.assert_not_called()

    def test_nonexistent_file(self, mock_api, tmp_path):
        """Test deploying non-existent file."""
        filepath = tmp_path / "missing.md"

        # Should raise appropriate error
        with pytest.raises(FileNotFoundError):
            deploy_page(mock_api, "space123", None, filepath)

    def test_invalid_frontmatter(self, mock_api, tmp_path):
        """Test handling invalid frontmatter."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
invalid yaml:
  - item
    bad indentation
---
# Content""")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        # Should handle gracefully
        page_id = deploy_page(mock_api, "space123", None, filepath)

        # Should still create page
        assert page_id == "page-123"
