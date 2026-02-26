"""
ADF Node Constructors
=====================
Pure functions that create Atlassian Document Format (ADF) nodes.

Each function returns a plain Python dict representing an ADF node.
No serialization or side effects.

Usage:
    from adf.nodes import paragraph, text_node

    p = paragraph([text_node("Hello world")])
"""

import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Image Width Constants & Helpers
# ---------------------------------------------------------------------------

# Safe maximum pixel width for images on a narrow (default) Confluence page.
# The Confluence narrow content area is ~760px. Images wider than this will
# overflow and look bad. Use this as the default for all images.
NARROW_PAGE_WIDTH_PX = 760


def resolve_image_width(width) -> tuple:
    """
    Resolve an image width specifier to (layout, pixel_width, width_type).

    Presets:
        None / "narrow" → center layout, 760px pixel width (narrow page default)
        "wide"          → "wide" layout (extends into page margins; width attrs ignored)
        "max"           → "full-width" layout (edge-to-edge; width attrs ignored)

    Custom:
        int or numeric string → center layout, that pixel width

    Returns:
        (layout, pixel_width, width_type) — pixel_width and width_type are None
        for "wide" and "full-width" layouts (Confluence ignores width for those).
    """
    if width is None or width == "narrow":
        return "center", NARROW_PAGE_WIDTH_PX, "pixel"
    if width == "wide":
        return "wide", None, None
    if width == "max":
        return "full-width", None, None
    try:
        return "center", int(width), "pixel"
    except (ValueError, TypeError):
        return "center", NARROW_PAGE_WIDTH_PX, "pixel"

# ---------------------------------------------------------------------------
# Block Nodes
# ---------------------------------------------------------------------------


def doc(content: list) -> dict:
    """Root ADF document node."""
    return {"version": 1, "type": "doc", "content": content}


def heading(level: int, content: list) -> dict:
    """ADF heading node (level 1–6). content is a list of inline nodes."""
    return {"type": "heading", "attrs": {"level": level}, "content": content}


def paragraph(content: list) -> dict:
    """ADF paragraph node. content is a list of inline nodes."""
    return {"type": "paragraph", "content": content}


def paragraph_with_alignment(content: list, align: str) -> dict:
    """
    ADF paragraph with text alignment.

    Applies alignment mark to the PARAGRAPH node, not individual text nodes.
    align: None (left/default) | 'center' | 'end' (right)

    Maps to storage format: <p style="text-align: center;">...</p>

    Note: ADF schema only allows 'center' and 'end' values.
    Left alignment is the default and requires no mark.
    """
    if not align:
        # Left alignment is default, no mark needed
        return paragraph(content)

    # Alignment is a mark on the paragraph node itself
    return {
        "type": "paragraph",
        "marks": [{"type": "alignment", "attrs": {"align": align}}],
        "content": content,
    }


def rule() -> dict:
    """ADF rule (horizontal divider) block node."""
    return {"type": "rule"}


def code_block(code: str, language: str = None) -> dict:
    """ADF codeBlock node. language is optional."""
    node = {
        "type": "codeBlock",
        "attrs": {"language": language} if language else {},
        "content": [{"type": "text", "text": code}],
    }
    return node


def blockquote(content: list) -> dict:
    """ADF blockquote node."""
    return {"type": "blockquote", "content": content}


def panel(panel_type: str, content: list) -> dict:
    """
    ADF panel node.
    panel_type: 'info' | 'note' | 'warning' | 'success' | 'error'
    """
    return {"type": "panel", "attrs": {"panelType": panel_type}, "content": content}


def expand(title: str, content: list) -> dict:
    """ADF expand (collapsible section) node."""
    return {"type": "expand", "attrs": {"title": title}, "content": content}


# ---------------------------------------------------------------------------
# List Nodes
# ---------------------------------------------------------------------------


def bullet_list(items: list) -> dict:
    """ADF bulletList node."""
    return {"type": "bulletList", "content": items}


def ordered_list(items: list, order: int = 1) -> dict:
    """ADF orderedList node. order sets the starting number."""
    return {"type": "orderedList", "attrs": {"order": order}, "content": items}


def task_list(items: list) -> dict:
    """ADF taskList node (checklist)."""
    return {
        "type": "taskList",
        "attrs": {"localId": str(uuid.uuid4())},
        "content": items,
    }


def task_item(state: str, content: list) -> dict:
    """
    ADF taskItem node (checkbox list item).
    state: 'TODO' | 'DONE'
    content: list of INLINE nodes (text, marks, etc.) — NOT paragraphs

    Unlike listItem which contains block nodes, taskItem contains inline nodes directly.
    """
    return {
        "type": "taskItem",
        "attrs": {"localId": str(uuid.uuid4()), "state": state},
        "content": content,
    }


def list_item(content: list) -> dict:
    """ADF listItem node. content is a list of block nodes (paragraph, nested list)."""
    return {"type": "listItem", "content": content}


# ---------------------------------------------------------------------------
# Table Nodes
# ---------------------------------------------------------------------------


def table_node(rows: list) -> dict:
    """ADF table node."""
    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": rows,
    }


def table_row(cells: list) -> dict:
    """ADF tableRow node."""
    return {"type": "tableRow", "content": cells}


def table_header(content: list, align: str = None) -> dict:
    """
    ADF tableHeader node.

    Note: alignment is NOT set on the cell itself, but on the paragraph content.
    Use paragraph_with_alignment() to create aligned content.
    """
    return {"type": "tableHeader", "attrs": {}, "content": content}


def table_cell(content: list, align: str = None) -> dict:
    """
    ADF tableCell node.

    Note: alignment is NOT set on the cell itself, but on the paragraph content.
    Use paragraph_with_alignment() to create aligned content.
    """
    return {"type": "tableCell", "attrs": {}, "content": content}


# ---------------------------------------------------------------------------
# Inline Nodes
# ---------------------------------------------------------------------------


def text_node(text: str, marks: list = None) -> dict:
    """ADF text inline node, optionally with marks."""
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def hard_break() -> dict:
    """ADF hardBreak inline node."""
    return {"type": "hardBreak"}


def inline_card(url: str) -> dict:
    """
    ADF inlineCard node.

    For Confluence internal page links produced from [Text](<Page Title>),
    the deploy tool replaces 'confluence-page://Page Title' with the actual
    page URL after looking up the page ID.
    """
    return {"type": "inlineCard", "attrs": {"url": url}}


def media_single(
    url: str = None,
    alt: str = None,
    file_id: str = None,
    collection: str = None,
    width=None,
) -> dict:
    """
    ADF mediaSingle node (image container).

    Supports two modes:
    1. External URL: Pass url parameter
    2. Attachment file: Pass file_id and collection parameters

    CONFLUENCE ATTACHMENT REQUIREMENTS:
    - Attachments use type: "file" with Media Services fileId and collection
    - collection format: "contentId-{pageId}"
    - External URLs use type: "external" with url

    IMAGE SIZING:
    Defaults to NARROW_PAGE_WIDTH_PX (760px) to prevent overflow on the default
    narrow Confluence page layout. Override with the width parameter:
        None / "narrow" → 760px (default, fits narrow page)
        "wide"          → Confluence "wide" layout (extends into margins)
        "max"           → Confluence "full-width" layout (edge-to-edge)
        int             → explicit pixel width (e.g. 500)

    Args:
        url: External image URL (for type: "external")
        alt: Alt text for accessibility
        file_id: Media Services fileId UUID (for type: "file")
        collection: Collection identifier "contentId-{pageId}" (for type: "file")
        width: Width specifier — None, "narrow", "wide", "max", or int pixels
    """
    if file_id and collection:
        # Attachment file mode
        media_attrs = {
            "type": "file",
            "id": file_id,
            "collection": collection,
        }
    elif url:
        # External URL mode
        media_attrs = {
            "type": "external",
            "url": url,
        }
    else:
        raise ValueError("Must provide either (file_id + collection) or url")

    if alt:
        media_attrs["alt"] = alt

    layout, pixel_width, width_type = resolve_image_width(width)
    media_single_attrs: dict = {"layout": layout}
    if pixel_width is not None:
        media_single_attrs["width"] = pixel_width
        media_single_attrs["widthType"] = width_type

    return {
        "type": "mediaSingle",
        "attrs": media_single_attrs,
        "content": [{"type": "media", "attrs": media_attrs}],
    }


def emoji_node(short_name: str) -> dict:
    """
    ADF emoji node.
    short_name should be the bare name without colons (e.g. 'rocket').
    """
    name = short_name.strip(":")
    return {
        "type": "emoji",
        "attrs": {"shortName": f":{name}:", "text": f":{name}:"},
    }


def status_node(text: str, color: str) -> dict:
    """
    ADF status node.
    color: 'neutral' | 'blue' | 'red' | 'yellow' | 'green' | 'purple'
    ADF expects uppercase color values.
    """
    return {
        "type": "status",
        "attrs": {
            "text": text,
            "color": color.upper(),
            "localId": str(uuid.uuid4()),
            "style": "",
        },
    }


def date_node(date_str: str) -> dict:
    """
    ADF date node.
    date_str: 'YYYY-MM-DD'
    ADF expects a millisecond UTC timestamp as a string.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        timestamp = str(int(dt.timestamp() * 1000))
    except ValueError:
        timestamp = "0"
    return {"type": "date", "attrs": {"timestamp": timestamp}}
