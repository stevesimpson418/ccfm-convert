"""Tests for deploy.orchestration module."""

from unittest.mock import Mock

import pytest

from ccfm_convert.deploy.orchestration import (
    deploy_page,
    deploy_tree,
    destroy_page,
    destroy_pages,
    ensure_page_hierarchy,
)


@pytest.fixture
def mock_api():
    """Create mock API for testing."""
    api = Mock()
    api.domain = "example.atlassian.net"
    api.find_page_by_title = Mock(return_value=None)
    api.find_child_page_by_title = Mock(return_value=None)
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

        parent_id, _ = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

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

        parent_id, _ = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

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

        parent_id, _ = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

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

    def test_page_content_with_global_ci_banner_text(self, mock_api, tmp_path):
        """ensure_page_hierarchy forwards ci_banner_text to .page_content.md pages."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text("---\npage_meta:\n  title: Team Page\n---\nContent")

        filepath = subdir / "child.md"

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "parent-123"

        ensure_page_hierarchy(
            mock_api, "space123", filepath, docs_root, ci_banner_text="Global banner"
        )

        call_args = mock_api.create_page.call_args
        body = call_args[0][3]
        banner_text = body["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == "Global banner"


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

        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", "parent-456", filepath)

        # Should use scoped child lookup, not space-wide
        mock_api.find_child_page_by_title.assert_called_once_with("parent-456", "Test")
        mock_api.find_page_by_title.assert_not_called()
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

    def test_deploy_page_passes_global_ci_banner_text(self, mock_api, tmp_path):
        """deploy_page forwards ci_banner_text to add_ci_banner."""
        filepath = tmp_path / "test.md"
        filepath.write_text("# Test")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", None, filepath, ci_banner_text="Global banner")

        # Verify create_page was called; banner text is embedded in the ADF body
        call_args = mock_api.create_page.call_args
        body = call_args[0][3]  # 4th positional arg is body
        banner_text = body["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == "Global banner"

    def test_deploy_page_frontmatter_overrides_global_ci_banner_text(self, mock_api, tmp_path):
        """Per-page frontmatter ci_banner_text overrides global value."""
        filepath = tmp_path / "test.md"
        filepath.write_text("---\ndeploy_config:\n  ci_banner_text: Page-specific\n---\n# Test")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-123"

        deploy_page(mock_api, "space123", None, filepath, ci_banner_text="Global banner")

        call_args = mock_api.create_page.call_args
        body = call_args[0][3]
        banner_text = body["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == "Page-specific"

    def test_frontmatter_parent_ignored_uses_directory_hierarchy(self, mock_api, tmp_path):
        """deploy_page ignores deprecated parent frontmatter and uses directory hierarchy."""
        filepath = tmp_path / "test.md"
        filepath.write_text("""---
page_meta:
  title: My Page
  parent: Explicit Parent
---
# Content""")
        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-page"

        import warnings

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            deploy_page(mock_api, "space123", "directory-parent-id", filepath)

        call_args = mock_api.create_page.call_args
        assert call_args[0][1] == "directory-parent-id"  # directory hierarchy, not overridden


class TestDeployPageScopedLookup:
    """Tests for scoped page lookup in deploy_page (issue #30)."""

    def test_uses_child_lookup_when_parent_id_provided(self, mock_api, tmp_path):
        """When parent_id is provided, deploy_page uses find_child_page_by_title."""
        filepath = tmp_path / "test.md"
        filepath.write_text("---\npage_meta:\n  title: My Page\n---\nContent")

        mock_api.find_child_page_by_title.return_value = "existing-child-123"

        page_id = deploy_page(mock_api, "space123", "parent-456", filepath)

        mock_api.find_child_page_by_title.assert_called_once_with("parent-456", "My Page")
        mock_api.find_page_by_title.assert_not_called()
        assert page_id == "existing-child-123"
        mock_api.update_page.assert_called_once()

    def test_uses_space_wide_lookup_when_no_parent_id(self, mock_api, tmp_path):
        """When parent_id is None, deploy_page uses find_page_by_title (space-wide)."""
        filepath = tmp_path / "test.md"
        filepath.write_text("---\npage_meta:\n  title: My Page\n---\nContent")

        mock_api.find_page_by_title.return_value = "existing-space-123"

        page_id = deploy_page(mock_api, "space123", None, filepath)

        mock_api.find_page_by_title.assert_called_with("space123", "My Page")
        mock_api.find_child_page_by_title.assert_not_called()
        assert page_id == "existing-space-123"
        mock_api.update_page.assert_called_once()

    def test_duplicate_titles_under_different_parents_disambiguated(self, mock_api, tmp_path):
        """Pages with same title under different parents are correctly disambiguated."""
        filepath_a = tmp_path / "guide_a.md"
        filepath_a.write_text("---\npage_meta:\n  title: Getting Started\n---\nTeam A content")
        filepath_b = tmp_path / "guide_b.md"
        filepath_b.write_text("---\npage_meta:\n  title: Getting Started\n---\nTeam B content")

        # First deploy under parent-A: no existing child, creates new
        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-a"

        page_id_a = deploy_page(mock_api, "space123", "parent-A", filepath_a)

        mock_api.find_child_page_by_title.assert_called_with("parent-A", "Getting Started")
        assert page_id_a == "page-a"

        # Reset mocks
        mock_api.reset_mock()

        # Second deploy under parent-B: no existing child, creates new
        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-b"

        page_id_b = deploy_page(mock_api, "space123", "parent-B", filepath_b)

        mock_api.find_child_page_by_title.assert_called_with("parent-B", "Getting Started")
        assert page_id_b == "page-b"

        # Each got its own page — no cross-contamination
        assert page_id_a != page_id_b


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

        parent_id, _ = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

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

    def test_symlink_escaping_docs_root_raises(self, mock_api, tmp_path):
        """Symlink inside docs_root that resolves outside it raises ValueError."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        # Create a symlink inside docs_root pointing to parent (outside docs_root)
        evil_link = docs_root / "escape"
        evil_link.symlink_to(tmp_path)

        # filepath appears to be inside docs/escape/
        filepath = evil_link / "page.md"

        with pytest.raises(ValueError, match="resolves outside docs_root"):
            ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

    def test_same_child_name_under_different_parents(self, mock_api, tmp_path):
        """Regression: two directories with the same child name deploy as separate pages.

        Given docs/Team/Engineering/ and docs/Admin/Engineering/, the two
        "Engineering" pages must be created separately under their respective
        parents, not collapsed into one because of a space-wide title match.
        """
        docs_root = tmp_path / "docs"
        (docs_root / "Team" / "Engineering").mkdir(parents=True)
        (docs_root / "Admin" / "Engineering").mkdir(parents=True)

        # Track created pages: title -> list of (parent_id, page_id)
        created = {}
        counter = [0]

        def mock_create(space_id, parent_id, title, body, status="current"):
            counter[0] += 1
            pid = f"page-{counter[0]}"
            created.setdefault(title, []).append((parent_id, pid))
            return pid

        # Space-wide search finds nothing (first-level dirs have no parent)
        mock_api.find_page_by_title.return_value = None
        # Child-scoped search finds nothing (each Engineering is new under its parent)
        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.side_effect = mock_create

        file_team = docs_root / "Team" / "Engineering" / "guide.md"
        file_admin = docs_root / "Admin" / "Engineering" / "policy.md"

        ensure_page_hierarchy(mock_api, "space123", file_team, docs_root)
        ensure_page_hierarchy(mock_api, "space123", file_admin, docs_root)

        # "Engineering" should have been created twice, under different parents
        assert len(created["Engineering"]) == 2
        team_parent = created["Engineering"][0][0]
        admin_parent = created["Engineering"][1][0]
        assert team_parent != admin_parent

        # Verify child lookup was used (not space-wide) for nested "Engineering"
        assert mock_api.find_child_page_by_title.call_count == 2

    def test_child_page_lookup_used_for_nested_levels(self, mock_api, tmp_path):
        """ensure_page_hierarchy uses find_child_page_by_title for nested dirs."""
        docs_root = tmp_path / "docs"
        (docs_root / "Team" / "Engineering").mkdir(parents=True)

        filepath = docs_root / "Team" / "Engineering" / "page.md"

        counter = [0]

        def mock_create(space_id, parent_id, title, body, status="current"):
            counter[0] += 1
            return f"page-{counter[0]}"

        mock_api.find_page_by_title.return_value = None
        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.side_effect = mock_create

        ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

        # First level "Team" — no parent, uses find_page_by_title
        mock_api.find_page_by_title.assert_called_once_with("space123", "Team")
        # Second level "Engineering" — has parent, uses find_child_page_by_title
        mock_api.find_child_page_by_title.assert_called_once_with("page-1", "Engineering")

    def test_filepath_not_under_docs_root_returns_none(self, mock_api, tmp_path):
        """Lines 33-35: when filepath is not relative to docs_root, returns None."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        # filepath lives outside docs_root
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        filepath = other_dir / "page.md"

        result, _ = ensure_page_hierarchy(mock_api, "space123", filepath, docs_root)

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

        deploy_tree(mock_api, "space123", docs_root)

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

        deploy_tree(mock_api, "space123", docs_root)

        # Should deploy all files
        assert mock_api.create_page.call_count >= 3

    def test_deploy_tree_passes_ci_banner_text(self, mock_api, tmp_path):
        """deploy_tree forwards ci_banner_text to each deployed page."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        file1 = docs_root / "test.md"
        file1.write_text("# Test")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        deploy_tree(mock_api, "space123", docs_root, ci_banner_text="Global banner")

        call_args = mock_api.create_page.call_args
        body = call_args[0][3]
        banner_text = body["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == "Global banner"

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

        deploy_tree(mock_api, "space123", docs_root)

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

        deploy_tree(mock_api, "space123", docs_root)

        # Should only deploy regular page (not .page_content.md)
        # Plus one for the container page created from .page_content.md
        assert mock_api.create_page.call_count >= 1

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
        deploy_tree(mock_api, "space123", docs_root)

        # Should have attempted both
        assert mock_api.create_page.call_count == 2


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

    def test_files_param_deploys_only_specified_files(self, mock_api, tmp_path):
        """deploy_tree with files= deploys only the provided files, not all in directory."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        file_a = docs_root / "alpha.md"
        file_b = docs_root / "beta.md"
        file_a.write_text("# Alpha")
        file_b.write_text("# Beta")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        # Only pass file_a — file_b should NOT be deployed
        deploy_tree(mock_api, "space123", docs_root, files=[file_a])

        # Exactly one page created (alpha only)
        assert mock_api.create_page.call_count == 1

    def test_files_param_preserves_ordering(self, mock_api, tmp_path):
        """deploy_tree with files= preserves the caller's ordering (e.g. dependency order)."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        # Create files with names that would sort alphabetically as alpha, beta, gamma
        file_alpha = docs_root / "alpha.md"
        file_beta = docs_root / "beta.md"
        file_gamma = docs_root / "gamma.md"
        file_alpha.write_text("# Alpha")
        file_beta.write_text("# Beta")
        file_gamma.write_text("# Gamma")

        created_titles = []

        def mock_create(space_id, parent_id, title, body, status="current"):
            created_titles.append(title)
            return f"page-{len(created_titles)}"

        mock_api.create_page.side_effect = mock_create
        mock_api.find_page_by_title.return_value = None

        # Pass files in reverse-alphabetical order (simulating dependency ordering)
        deploy_tree(mock_api, "space123", docs_root, files=[file_gamma, file_beta, file_alpha])

        # Pages must be created in the exact order provided, not sorted alphabetically
        assert created_titles == ["Gamma", "Beta", "Alpha"]

    def test_files_param_none_uses_rglob(self, mock_api, tmp_path):
        """deploy_tree with files=None discovers all .md files via rglob."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        (docs_root / "one.md").write_text("# One")
        (docs_root / "two.md").write_text("# Two")

        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "page-123"

        deploy_tree(mock_api, "space123", docs_root, files=None)

        # Both files discovered and deployed
        assert mock_api.create_page.call_count == 2

    def test_files_param_preserves_hierarchy(self, mock_api, tmp_path):
        """deploy_tree with files= still creates parent pages for nested files."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "section"
        subdir.mkdir(parents=True)

        nested = subdir / "page.md"
        nested.write_text("# Nested Page")

        call_count = [0]

        def mock_create(space_id, parent_id, title, body, status="current"):
            call_count[0] += 1
            return f"page-{call_count[0]}"

        mock_api.create_page.side_effect = mock_create
        mock_api.find_page_by_title.return_value = None

        deploy_tree(mock_api, "space123", docs_root, files=[nested])

        # Should create container page for "section" + the actual page
        assert mock_api.create_page.call_count == 2

    def test_empty_directory(self, mock_api, tmp_path):
        """Test deploying empty directory."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        # Should not crash
        deploy_tree(mock_api, "space123", docs_root)

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


class TestDestroyPage:
    """Tests for destroy_page.

    destroy_page uses api.delete_page() (v2 DELETE) because the Confluence Cloud
    v2 PUT endpoint only accepts CURRENT or DRAFT as status values. DELETE moves
    the page to the site trash.
    """

    def test_destroy_page_success_returns_true(self, mock_api):
        """destroy_page calls api.delete_page and returns True on success."""
        result = destroy_page(mock_api, "page-42", "My Page")

        assert result is True
        mock_api.delete_page.assert_called_once_with("page-42")

    def test_destroy_page_exception_returns_false(self, mock_api):
        """destroy_page catches exceptions from delete_page and returns False."""
        mock_api.delete_page.side_effect = RuntimeError("API down")

        result = destroy_page(mock_api, "page-99", "Broken Page")

        assert result is False

    def test_destroy_page_prints_success_message(self, mock_api, capsys):
        """destroy_page prints confirmation with title and page_id on success."""
        destroy_page(mock_api, "page-1", "Published Title")

        captured = capsys.readouterr()
        assert "Published Title" in captured.out
        assert "page-1" in captured.out

    def test_destroy_page_prints_warning_on_failure(self, mock_api, capsys):
        """destroy_page prints a warning on failure."""
        mock_api.delete_page.side_effect = RuntimeError("timeout")

        destroy_page(mock_api, "page-2", "Failed Page")

        captured = capsys.readouterr()
        assert "Failed Page" in captured.out


class TestDestroyPages:
    """Tests for destroy_pages — batch destroy with state removal."""

    def test_destroy_pages_deletes_and_removes_from_state(self, mock_api):
        """destroy_pages calls destroy_page for each action and removes from state."""
        from ccfm_convert.plan.planner import DestroyAction

        state = Mock()
        actions = [
            DestroyAction(rel_path="docs/page.md", page_id="p1", title="Page"),
        ]

        count = destroy_pages(mock_api, state, actions)

        assert count == 1
        mock_api.delete_page.assert_called_once_with("p1")
        state.remove_page.assert_called_once_with("docs/page.md")

    def test_destroy_pages_preserves_order(self, mock_api):
        """destroy_pages executes in the order provided (planner pre-sorts deepest-first)."""
        from ccfm_convert.plan.planner import DestroyAction

        state = Mock()
        # Pre-sorted deepest-first by the planner
        actions = [
            DestroyAction(rel_path="docs/team/sub/page.md", page_id="p1", title="Page"),
            DestroyAction(rel_path="docs/team/sub", page_id="d2", title="Sub"),
            DestroyAction(rel_path="docs/team", page_id="d1", title="Team"),
        ]

        delete_order = []
        mock_api.delete_page.side_effect = lambda pid: delete_order.append(pid)

        destroy_pages(mock_api, state, actions)

        assert delete_order == ["p1", "d2", "d1"]

    def test_destroy_pages_partial_failure(self, mock_api):
        """destroy_pages continues on failure and only removes successful entries from state."""
        from ccfm_convert.plan.planner import DestroyAction

        state = Mock()
        actions = [
            DestroyAction(rel_path="docs/a.md", page_id="p1", title="A"),
            DestroyAction(rel_path="docs/b.md", page_id="p2", title="B"),
        ]

        # First succeeds, second fails
        mock_api.delete_page.side_effect = [None, RuntimeError("fail")]

        count = destroy_pages(mock_api, state, actions)

        assert count == 1
        state.remove_page.assert_called_once_with("docs/a.md")

    def test_destroy_pages_empty_list(self, mock_api):
        """destroy_pages with empty list returns 0."""
        state = Mock()
        count = destroy_pages(mock_api, state, [])

        assert count == 0
        mock_api.delete_page.assert_not_called()


class TestChangedContainersParam:
    """Tests for the changed_containers parameter in ensure_page_hierarchy."""

    def test_unchanged_container_skips_update(self, mock_api, tmp_path):
        """Existing page with .page_content.md is NOT updated when not in changed_containers."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text(
            "---\npage_meta:\n  title: Team\n  labels:\n    - team\n---\n# Team"
        )
        filepath = subdir / "child.md"

        mock_api.find_page_by_title.return_value = "existing-team-page"

        # changed_containers does NOT include "Team"
        parent_id, _ = ensure_page_hierarchy(
            mock_api, "space123", filepath, docs_root, changed_containers=set()
        )

        assert parent_id == "existing-team-page"
        # update_page should NOT be called since Team is not in changed_containers
        mock_api.update_page.assert_not_called()
        mock_api.add_labels.assert_not_called()

    def test_changed_container_triggers_update(self, mock_api, tmp_path):
        """Existing page with .page_content.md IS updated when in changed_containers."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text(
            "---\npage_meta:\n  title: Team\n  labels:\n    - team\n---\n# Team"
        )
        filepath = subdir / "child.md"

        mock_api.find_page_by_title.return_value = "existing-team-page"

        # changed_containers includes "Team"
        parent_id, _ = ensure_page_hierarchy(
            mock_api, "space123", filepath, docs_root, changed_containers={"Team"}
        )

        assert parent_id == "existing-team-page"
        mock_api.update_page.assert_called_once()

    def test_none_changed_containers_updates_all(self, mock_api, tmp_path):
        """When changed_containers is None (default), all containers are updated."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text(
            "---\npage_meta:\n  title: Team\n  labels:\n    - team\n---\n# Team"
        )
        filepath = subdir / "child.md"

        mock_api.find_page_by_title.return_value = "existing-team-page"

        parent_id, _ = ensure_page_hierarchy(
            mock_api, "space123", filepath, docs_root, changed_containers=None
        )

        assert parent_id == "existing-team-page"
        mock_api.update_page.assert_called_once()

    def test_nested_changed_container_only_updates_changed(self, mock_api, tmp_path):
        """Only the changed nested directory is updated, not unchanged parents."""
        docs_root = tmp_path / "docs"
        parent_dir = docs_root / "Team"
        child_dir = parent_dir / "Engineering"
        child_dir.mkdir(parents=True)

        # Both directories have .page_content.md
        (parent_dir / ".page_content.md").write_text("---\npage_meta:\n  title: Team\n---\n# Team")
        (child_dir / ".page_content.md").write_text(
            "---\npage_meta:\n  title: Engineering\n---\n# Engineering"
        )

        filepath = child_dir / "page.md"

        # Both pages exist
        mock_api.find_page_by_title.return_value = "team-page"
        mock_api.find_child_page_by_title.return_value = "eng-page"

        # Only Engineering changed, not Team
        parent_id, _ = ensure_page_hierarchy(
            mock_api,
            "space123",
            filepath,
            docs_root,
            changed_containers={"Team/Engineering"},
        )

        # update_page should be called only once (for Engineering, not Team)
        mock_api.update_page.assert_called_once()
        call_args = mock_api.update_page.call_args[0]
        assert call_args[0] == "eng-page"  # page_id for Engineering

    def test_new_page_creation_unaffected_by_changed_containers(self, mock_api, tmp_path):
        """New pages are always created regardless of changed_containers."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        page_content = subdir / ".page_content.md"
        page_content.write_text("---\npage_meta:\n  title: Team\n---\n# Team")
        filepath = subdir / "child.md"

        # Page does NOT exist yet
        mock_api.find_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-team-page"

        parent_id, _ = ensure_page_hierarchy(
            mock_api, "space123", filepath, docs_root, changed_containers=set()
        )

        # Should still create the page even though changed_containers is empty
        assert parent_id == "new-team-page"
        mock_api.create_page.assert_called_once()

    def test_deploy_tree_forwards_changed_containers(self, mock_api, tmp_path):
        """deploy_tree forwards changed_containers to ensure_page_hierarchy."""
        docs_root = tmp_path / "docs"
        subdir = docs_root / "Team"
        subdir.mkdir(parents=True)

        # .page_content.md exists but is NOT in changed set
        (subdir / ".page_content.md").write_text("---\npage_meta:\n  title: Team\n---\n# Team")

        child = subdir / "page.md"
        child.write_text("# Page")

        mock_api.find_page_by_title.return_value = "existing-team"
        mock_api.find_child_page_by_title.return_value = None
        mock_api.create_page.return_value = "new-page"

        deploy_tree(mock_api, "space123", docs_root, changed_containers=set())

        # update_page should NOT be called for the container since it's not changed
        # It should only be called for the child page if it already existed
        # In this case the child is new so create_page is called
        for call in mock_api.update_page.call_args_list:
            # Ensure no update_page call was for the container title "Team"
            assert call[0][1] != "Team"
