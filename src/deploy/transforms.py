"""ADF Document Transformations."""

import os
from datetime import UTC, datetime

from adf.inline import parse_inline_with_breaks
from adf.nodes import expand, paragraph, resolve_image_width


def add_ci_banner(adf_doc, git_url="", banner_text=None, metadata=None):
    """
    Prepend CI banner to ADF document.

    Args:
        adf_doc: The ADF document dict
        git_url: Optional git file URL
        banner_text: Optional custom banner text
        metadata: Optional metadata dict for metadata expand block
    """
    # Default banner text
    if not banner_text:
        banner_text = (
            "⚠️ This page is automatically generated and deployed. Manual edits may be overwritten."
        )

    banner_content = [{"type": "text", "text": banner_text}]

    # Add git link if provided
    if git_url:
        banner_content.extend(
            [
                {"type": "text", "text": " View source: "},
                {
                    "type": "text",
                    "text": "source",
                    "marks": [{"type": "link", "attrs": {"href": git_url}}],
                },
            ]
        )

    banner_panel = {
        "type": "panel",
        "attrs": {"panelType": "info"},
        "content": [{"type": "paragraph", "content": banner_content}],
    }

    # Prepend banner to document content
    adf_doc["content"].insert(0, banner_panel)

    # Add metadata expand if requested
    if metadata and metadata.get("include_page_metadata"):
        metadata_expand = create_metadata_expand(metadata, git_url)
        adf_doc["content"].insert(1, metadata_expand)

    return adf_doc


def create_metadata_expand(metadata, git_url=""):
    """Create an expand block with page metadata."""
    lines = []

    # Author
    author = metadata.get("author", "Not specified")
    lines.append(f"**Author:** {author}")

    # Last updated (current timestamp)
    last_updated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"**Last Updated:** {last_updated}")

    # Labels
    labels = metadata.get("labels", [])
    if labels:
        labels_text = ", ".join(labels)
        lines.append(f"**Labels:** {labels_text}")

    # Git file path
    if git_url:
        lines.append(f"**Source:** [{git_url}]({git_url})")

    # Page status
    page_status = metadata.get("page_status", "current")
    lines.append(f"**Status:** {page_status}")

    # Join with hard breaks and parse as inline markdown
    text_with_breaks = "  \n".join(lines)  # Two spaces + newline = hard break
    inline_content = parse_inline_with_breaks(text_with_breaks)

    return expand("📋 Page Metadata", [paragraph(inline_content)])


def resolve_page_links(adf_doc, api, space_id):
    """
    Walk the ADF document and resolve confluence-page:// URLs to actual page URLs.

    Modifies the document in place, replacing:
      confluence-page://Page Title
    with:
      https://domain/wiki/pages/12345
    """

    def walk(node):
        if isinstance(node, dict):
            # Check if this is an inlineCard with a sentinel URL
            if node.get("type") == "inlineCard":
                url = node.get("attrs", {}).get("url", "")
                if url.startswith("confluence-page://"):
                    page_title = url.replace("confluence-page://", "")
                    real_url = api.find_page_webui_url(space_id, page_title)
                    if real_url:
                        node["attrs"]["url"] = real_url
                    else:
                        print(f"   ⚠️  Warning: Page not found for link: {page_title}")

            # Recurse into all values
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(adf_doc)
    return adf_doc


def resolve_attachment_media_nodes(adf_doc, attachment_map, page_id):
    """
    Walk the ADF document and convert media nodes from external URLs to file attachments.

    CONFLUENCE API WORKAROUND:
    Due to API limitations, we must:
    1. Create page with images as external URLs (or placeholders)
    2. Upload attachments to get fileIds
    3. Update page with correct file media nodes

    Args:
        adf_doc: The ADF document dict
        attachment_map: Dict mapping filename -> {
            'id': attachmentId,
            'fileId': mediaServicesId,
            'display_width': width specifier or None,
        }
        page_id: Page ID for collection identifier

    Transforms mediaSingle + media nodes from:
        mediaSingle > media {"type": "external", "url": "diagram.png"}
    To:
        mediaSingle > media {"type": "file", "id": "uuid", "collection": "contentId-{pageId}"}

    Also applies display_width from the attachment map to the mediaSingle attrs when set.
    """
    collection = f"contentId-{page_id}"

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "mediaSingle":
                # Process the child media node with access to the parent mediaSingle
                for media_node in node.get("content", []):
                    if media_node.get("type") == "media":
                        attrs = media_node.get("attrs", {})
                        url = attrs.get("url", "")
                        filename = os.path.basename(url)

                        if filename in attachment_map:
                            entry = attachment_map[filename]
                            file_id = entry["fileId"]
                            alt = attrs.get("alt")

                            # Replace media attrs with file attachment structure
                            media_node["attrs"] = {
                                "type": "file",
                                "id": file_id,
                                "collection": collection,
                            }
                            if alt:
                                media_node["attrs"]["alt"] = alt

                            # Apply display_width override to parent mediaSingle if specified
                            display_width = entry.get("display_width")
                            if display_width is not None:
                                layout, pixel_width, width_type = resolve_image_width(display_width)
                                node["attrs"]["layout"] = layout
                                if pixel_width is not None:
                                    node["attrs"]["width"] = pixel_width
                                    node["attrs"]["widthType"] = width_type
                                else:
                                    # wide/full-width layouts ignore width attrs
                                    node["attrs"].pop("width", None)
                                    node["attrs"].pop("widthType", None)

            # Recurse into all values
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(adf_doc)
    return adf_doc
