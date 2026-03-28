"""ADF-to-Markdown reverse converter.

Converts an Atlassian Document Format (ADF) document dict back into
Confluence Cloud Flavoured Markdown (CCFM).

Usage:
    from ccfm_convert.adf.reverse import adf_to_markdown

    markdown = adf_to_markdown(adf_dict)

Phase 1 supports: headings, paragraphs, ordered lists, inline marks,
and hard breaks. Unknown node types are silently skipped.
"""

from __future__ import annotations


def adf_to_markdown(adf_doc: dict) -> str:
    """Convert an ADF document dict to CCFM markdown string."""
    content = adf_doc.get("content", [])
    if not content:
        return ""

    blocks: list[str] = []
    for node in content:
        result = _convert_node(node)
        if result is not None:
            blocks.append(result)

    if not blocks:
        return ""

    return "\n\n".join(blocks) + "\n"


def _convert_node(node: dict) -> str | None:
    """Dispatch a top-level block node to its handler. Returns None for unknown types."""
    handler = _NODE_HANDLERS.get(node.get("type"))
    if handler is None:
        return None
    return handler(node)


# ── Inline rendering ─────────────────────────────────────────────────


def _render_inline_content(content: list[dict]) -> str:
    """Render a list of inline nodes (text, hardBreak) to markdown."""
    parts = []
    for node in content:
        node_type = node.get("type")
        if node_type == "text":
            parts.append(_render_text_node(node))
        elif node_type == "hardBreak":
            parts.append("\\\n")
    return "".join(parts)


# Mark wrapping order: outermost → innermost.
# link wraps everything; code is innermost (no nesting inside code spans).
_MARK_ORDER = ["link", "strong", "em", "strike", "underline", "subsup", "code"]


def _render_text_node(node: dict) -> str:
    """Render a single text node, applying mark wrappers."""
    text = node.get("text", "")
    marks = node.get("marks", [])
    if not marks:
        return text

    mark_types = {m["type"] for m in marks}
    mark_map = {m["type"]: m for m in marks}

    # Special case: bold+italic combined → ***text***
    if "strong" in mark_types and "em" in mark_types:
        text = f"***{text}***"
        mark_types -= {"strong", "em"}
    else:
        if "strong" in mark_types:
            text = f"**{text}**"
            mark_types.discard("strong")
        if "em" in mark_types:
            text = f"*{text}*"
            mark_types.discard("em")

    if "strike" in mark_types:
        text = f"~~{text}~~"
        mark_types.discard("strike")

    if "underline" in mark_types:
        text = f"++{text}++"
        mark_types.discard("underline")

    if "subsup" in mark_types:
        subsup_mark = mark_map["subsup"]
        sub_type = subsup_mark.get("attrs", {}).get("type", "sup")
        if sub_type == "sup":
            text = f"^{text}^"
        else:
            text = f"~{text}~"
        mark_types.discard("subsup")

    if "code" in mark_types:
        text = f"`{text}`"
        mark_types.discard("code")

    if "link" in mark_types:
        link_mark = mark_map["link"]
        href = link_mark.get("attrs", {}).get("href", "")
        text = f"[{text}]({href})"
        mark_types.discard("link")

    return text


# ── Block handlers ───────────────────────────────────────────────────


def _convert_paragraph(node: dict) -> str:
    """Convert a paragraph node to markdown."""
    content = node.get("content", [])
    if not content:
        return ""
    return _render_inline_content(content)


def _convert_heading(node: dict) -> str:
    """Convert a heading node to markdown."""
    level = node.get("attrs", {}).get("level", 1)
    content = node.get("content", [])
    prefix = "#" * level
    text = _render_inline_content(content) if content else ""
    return f"{prefix} {text}"


def _convert_ordered_list(node: dict) -> str:
    """Convert an orderedList node to markdown."""
    items = node.get("content", [])
    start = node.get("attrs", {}).get("order", 1)
    lines = []
    for i, item in enumerate(items):
        num = start + i
        # listItem wraps paragraph(s) — render the first paragraph's inline content
        item_content = item.get("content", [])
        if item_content:
            # Render the first block (typically a paragraph)
            first_block = item_content[0]
            block_content = first_block.get("content", [])
            text = _render_inline_content(block_content) if block_content else ""
        else:
            text = ""
        lines.append(f"{num}. {text}")
    return "\n".join(lines)


# ── Handler registry ─────────────────────────────────────────────────

_NODE_HANDLERS: dict[str, callable] = {
    "heading": _convert_heading,
    "paragraph": _convert_paragraph,
    "orderedList": _convert_ordered_list,
}
