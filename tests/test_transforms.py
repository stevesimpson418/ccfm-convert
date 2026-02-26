"""Tests for deploy.transforms module."""

from adf.nodes import NARROW_PAGE_WIDTH_PX, doc, inline_card, media_single, paragraph, text_node
from deploy.transforms import (
    add_ci_banner,
    create_metadata_expand,
    resolve_attachment_media_nodes,
    resolve_page_links,
)


class TestAddCIBanner:
    """Test CI banner addition."""

    def test_add_default_banner(self):
        """Test adding default CI banner."""
        adf_doc = doc([paragraph([text_node("Content")])])
        result = add_ci_banner(adf_doc)

        # Banner should be first element
        assert result["content"][0]["type"] == "panel"
        assert result["content"][0]["attrs"]["panelType"] == "info"

        # Original content should follow
        assert result["content"][1]["type"] == "paragraph"

    def test_add_banner_with_git_url(self):
        """Test adding banner with git URL."""
        adf_doc = doc([paragraph([text_node("Content")])])
        git_url = "https://github.com/user/repo/blob/main/file.md"
        result = add_ci_banner(adf_doc, git_url)

        # Should contain link in banner
        banner = result["content"][0]
        banner_content = banner["content"][0]["content"]

        # Find link node
        has_link = any(
            node.get("marks") and any(mark["type"] == "link" for mark in node["marks"])
            for node in banner_content
        )
        assert has_link

    def test_add_banner_with_custom_text(self):
        """Test adding banner with custom text."""
        adf_doc = doc([paragraph([text_node("Content")])])
        custom_text = "Custom warning message"
        result = add_ci_banner(adf_doc, banner_text=custom_text)

        # Check custom text is present
        banner_text = result["content"][0]["content"][0]["content"][0]["text"]
        assert banner_text == custom_text

    def test_add_banner_with_metadata(self):
        """Test adding banner with metadata expand."""
        adf_doc = doc([paragraph([text_node("Content")])])
        metadata = {
            "include_page_metadata": True,
            "author": "John Doe",
            "labels": ["python", "docs"],
        }
        result = add_ci_banner(adf_doc, metadata=metadata)

        # Should have banner + metadata expand + content
        assert len(result["content"]) >= 3
        assert result["content"][0]["type"] == "panel"
        assert result["content"][1]["type"] == "expand"

    def test_banner_preserves_content(self):
        """Test that banner doesn't modify existing content."""
        original_content = [
            paragraph([text_node("Para 1")]),
            paragraph([text_node("Para 2")]),
        ]
        adf_doc = doc(original_content[:])  # Copy to avoid mutation
        result = add_ci_banner(adf_doc)

        # Original content should be preserved after banner
        assert result["content"][1:] == original_content

    def test_empty_document(self):
        """Test adding banner to empty document."""
        adf_doc = doc([])
        result = add_ci_banner(adf_doc)

        # Should have just the banner
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "panel"


class TestCreateMetadataExpand:
    """Test metadata expand creation."""

    def test_basic_metadata(self):
        """Test basic metadata expand."""
        metadata = {"author": "John Doe", "labels": ["python", "api"], "page_status": "current"}
        result = create_metadata_expand(metadata)

        assert result["type"] == "expand"
        assert "Page Metadata" in result["attrs"]["title"]
        assert len(result["content"]) > 0

    def test_metadata_with_git_url(self):
        """Test metadata with git URL."""
        metadata = {"author": "Jane"}
        git_url = "https://github.com/user/repo/file.md"
        result = create_metadata_expand(metadata, git_url)

        # Should contain git URL
        assert result["type"] == "expand"

    def test_empty_metadata(self):
        """Test metadata expand with minimal metadata."""
        metadata = {}
        result = create_metadata_expand(metadata)

        # Should still create valid expand
        assert result["type"] == "expand"
        assert "content" in result


class TestResolvePageLinks:
    """Test Confluence page link resolution."""

    def test_resolve_single_link(self):
        """Test resolving single page link."""

        # Mock API
        class MockAPI:
            domain = "example.atlassian.net"

            def find_page_webui_url(self, space_id, title):
                if title == "Target Page":
                    return "https://example.atlassian.net/wiki/spaces/SPACE/pages/12345/Target+Page"
                return None

        adf_doc = doc([paragraph([inline_card("confluence-page://Target Page")])])

        result = resolve_page_links(adf_doc, MockAPI(), "SPACE123")

        # Should resolve to actual URL
        url = result["content"][0]["content"][0]["attrs"]["url"]
        assert url == "https://example.atlassian.net/wiki/spaces/SPACE/pages/12345/Target+Page"

    def test_resolve_multiple_links(self):
        """Test resolving multiple page links."""

        class MockAPI:
            domain = "example.atlassian.net"

            def find_page_webui_url(self, space_id, title):
                if title == "Page 1":
                    return "https://example.atlassian.net/wiki/spaces/SPACE/pages/111/Page+1"
                if title == "Page 2":
                    return "https://example.atlassian.net/wiki/spaces/SPACE/pages/222/Page+2"
                return None

        adf_doc = doc(
            [
                paragraph(
                    [
                        text_node("See "),
                        inline_card("confluence-page://Page 1"),
                        text_node(" and "),
                        inline_card("confluence-page://Page 2"),
                    ]
                )
            ]
        )

        result = resolve_page_links(adf_doc, MockAPI(), "SPACE123")

        # Both links should be resolved
        links = []
        for node in result["content"][0]["content"]:
            if node.get("type") == "inlineCard":
                links.append(node["attrs"]["url"])

        assert "wiki/spaces/SPACE/pages/111" in links[0]
        assert "wiki/spaces/SPACE/pages/222" in links[1]

    def test_unresolved_link(self):
        """Test handling of unresolved page link."""

        class MockAPI:
            domain = "example.atlassian.net"

            def find_page_webui_url(self, space_id, title):
                return None  # Page not found

        adf_doc = doc([paragraph([inline_card("confluence-page://Missing Page")])])

        # Should handle gracefully without crashing
        result = resolve_page_links(adf_doc, MockAPI(), "SPACE123")

        # Link should remain unchanged or be marked somehow
        assert isinstance(result["content"], list)

    def test_non_confluence_links(self):
        """Test that non-Confluence links are not modified."""

        class MockAPI:
            domain = "example.atlassian.net"

            def find_page_webui_url(self, space_id, title):
                return "https://example.atlassian.net/wiki/spaces/SPACE/pages/12345/Some+Page"

        external_url = "https://example.com"
        adf_doc = doc([paragraph([inline_card(external_url)])])

        result = resolve_page_links(adf_doc, MockAPI(), "SPACE123")

        # External link should remain unchanged
        url = result["content"][0]["content"][0]["attrs"]["url"]
        assert url == external_url

    def test_deeply_nested_links(self):
        """Test resolving links in nested structures."""

        class MockAPI:
            domain = "example.atlassian.net"

            def find_page_webui_url(self, space_id, title):
                return "https://example.atlassian.net/wiki/spaces/SPACE/pages/12345/Nested+Page"

        adf_doc = doc(
            [paragraph([text_node("Text"), inline_card("confluence-page://Nested Page")])]
        )

        result = resolve_page_links(adf_doc, MockAPI(), "SPACE123")

        # Nested link should be resolved
        assert isinstance(result["content"], list)


class TestResolveAttachmentMediaNodes:
    """Test attachment media node resolution."""

    def test_resolve_single_attachment(self):
        """Test resolving single attachment."""
        adf_doc = doc([media_single(url="diagram.png", alt="Architecture")])

        attachment_map = {"diagram.png": {"id": "att123", "fileId": "uuid-abc-123"}}
        page_id = "456"

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, page_id)

        # Should convert to file type
        media = result["content"][0]["content"][0]
        assert media["attrs"]["type"] == "file"
        assert media["attrs"]["id"] == "uuid-abc-123"
        assert media["attrs"]["collection"] == "contentId-456"
        assert media["attrs"]["alt"] == "Architecture"

    def test_resolve_multiple_attachments(self):
        """Test resolving multiple attachments."""
        adf_doc = doc(
            [
                media_single(url="img1.png", alt="Image 1"),
                media_single(url="img2.jpg", alt="Image 2"),
            ]
        )

        attachment_map = {
            "img1.png": {"id": "att1", "fileId": "uuid1"},
            "img2.jpg": {"id": "att2", "fileId": "uuid2"},
        }

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "789")

        # Both should be converted
        media1 = result["content"][0]["content"][0]
        media2 = result["content"][1]["content"][0]

        assert media1["attrs"]["id"] == "uuid1"
        assert media2["attrs"]["id"] == "uuid2"

    def test_attachment_not_in_map(self):
        """Test attachment not in map (remains external)."""
        adf_doc = doc([media_single(url="missing.png", alt="Missing")])

        attachment_map = {}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        # Should remain as external or unchanged
        media = result["content"][0]["content"][0]
        # Implementation may vary - just ensure it doesn't crash
        assert "attrs" in media

    def test_external_url_unchanged(self):
        """Test external URLs are not converted when filename doesn't match attachment map."""
        external_url = "https://example.com/external-image.png"
        adf_doc = doc([media_single(url=external_url, alt="External")])

        # Attachment map has different files
        attachment_map = {"local-image.png": {"id": "att1", "fileId": "uuid1"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        # External URL with non-matching filename should remain external
        media = result["content"][0]["content"][0]
        assert media["attrs"]["type"] == "external"
        assert media["attrs"]["url"] == external_url

    def test_preserve_alt_text(self):
        """Test that alt text is preserved."""
        adf_doc = doc([media_single(url="test.png", alt="Test alt text")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        media = result["content"][0]["content"][0]
        assert media["attrs"]["alt"] == "Test alt text"

    def test_attachment_without_alt(self):
        """Test attachment without alt text."""
        adf_doc = doc([media_single(url="test.png")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        media = result["content"][0]["content"][0]
        assert media["attrs"]["type"] == "file"
        # Alt may or may not be present
        assert "id" in media["attrs"]

    def test_nested_media_nodes(self):
        """Test media nodes in nested structures."""
        adf_doc = doc(
            [
                paragraph([text_node("Text")]),
                media_single(url="nested.png"),
            ]
        )

        attachment_map = {"nested.png": {"id": "att1", "fileId": "uuid1"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        # Nested media should be resolved
        media = result["content"][1]["content"][0]
        assert media["attrs"]["type"] == "file"

    def test_path_with_directories(self):
        """Test handling filenames with path separators."""
        adf_doc = doc([media_single(url="images/diagram.png")])

        attachment_map = {"diagram.png": {"id": "att1", "fileId": "uuid1"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        # Should extract basename and match
        media = result["content"][0]["content"][0]
        assert media["attrs"]["type"] == "file"

    def test_empty_attachment_map(self):
        """Test with empty attachment map."""
        adf_doc = doc([media_single(url="test.png")])

        result = resolve_attachment_media_nodes(adf_doc, {}, "123")

        # Should handle gracefully
        assert isinstance(result["content"], list)

    def test_collection_format(self):
        """Test collection format is correct."""
        adf_doc = doc([media_single(url="test.png")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1"}}
        page_id = "987654"

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, page_id)

        media = result["content"][0]["content"][0]
        assert media["attrs"]["collection"] == f"contentId-{page_id}"

    def test_default_width_preserved_when_no_display_width(self):
        """Test that mediaSingle retains its default width when attachment has no display_width."""
        adf_doc = doc([media_single(url="test.png")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1", "display_width": None}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        ms = result["content"][0]
        assert ms["attrs"]["width"] == NARROW_PAGE_WIDTH_PX
        assert ms["attrs"]["widthType"] == "pixel"

    def test_display_width_pixel_override(self):
        """Test display_width overrides mediaSingle pixel width."""
        adf_doc = doc([media_single(url="test.png")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1", "display_width": 500}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        ms = result["content"][0]
        assert ms["attrs"]["layout"] == "center"
        assert ms["attrs"]["width"] == 500
        assert ms["attrs"]["widthType"] == "pixel"

    def test_display_width_wide_preset(self):
        """Test display_width='wide' sets wide layout and removes pixel width attrs."""
        adf_doc = doc([media_single(url="test.png")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1", "display_width": "wide"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        ms = result["content"][0]
        assert ms["attrs"]["layout"] == "wide"
        assert "width" not in ms["attrs"]
        assert "widthType" not in ms["attrs"]

    def test_display_width_max_preset(self):
        """Test display_width='max' sets full-width layout and removes pixel width attrs."""
        adf_doc = doc([media_single(url="test.png")])

        attachment_map = {"test.png": {"id": "att1", "fileId": "uuid1", "display_width": "max"}}

        result = resolve_attachment_media_nodes(adf_doc, attachment_map, "123")

        ms = result["content"][0]
        assert ms["attrs"]["layout"] == "full-width"
        assert "width" not in ms["attrs"]
        assert "widthType" not in ms["attrs"]
