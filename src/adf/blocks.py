"""
Block Parsing
=============
Parses block-level markdown (document structure) into ADF block nodes.

Handles: tables, lists (bullet/ordered/task), blockquotes, panels, expands.

Usage:
    from adf.blocks import parse_table, build_list

    table_lines = ["| A | B |", "|---|---|", "| 1 | 2 |"]
    table_node = parse_table(table_lines)
"""

import re

from .inline import parse_inline, parse_inline_with_breaks
from .nodes import (
    blockquote,
    bullet_list,
    code_block,
    expand,
    list_item,
    ordered_list,
    panel,
    paragraph,
    paragraph_with_alignment,
    table_cell,
    table_header,
    table_node,
    table_row,
    task_item,
    task_list,
)

# ---------------------------------------------------------------------------
# Block Content Helpers
# ---------------------------------------------------------------------------

_PANEL_TYPES = {"info", "note", "warning", "success", "error"}


def parse_blockquote_block(quote_lines: list) -> dict:
    """
    Given lines stripped of their leading '> ', determine the block type
    (panel, expand, or plain blockquote) and return the appropriate ADF node.

    Args:
        quote_lines: Lines with '> ' prefix already removed

    Returns:
        ADF node (panel, expand, or blockquote)
    """
    if not quote_lines:
        return blockquote([paragraph([])])

    first = quote_lines[0].strip()

    # Panel: [!type]
    panel_match = re.match(r"^\[!(\w+)\]$", first)
    if panel_match:
        ptype = panel_match.group(1).lower()
        if ptype in _PANEL_TYPES:
            body_nodes = parse_block_content(quote_lines[1:])
            return panel(ptype, body_nodes)

    # Expand: [!expand Some Title Here]
    expand_match = re.match(r"^\[!expand\s+(.+)\]$", first, re.IGNORECASE)
    if expand_match:
        title = expand_match.group(1).strip()
        body_nodes = parse_block_content(quote_lines[1:])
        return expand(title, body_nodes)

    # Plain blockquote
    return blockquote(parse_block_content(quote_lines))


def parse_block_content(lines: list) -> list:
    """
    Convert a list of text lines into a list of ADF block nodes.
    Handles paragraphs and code blocks.

    Used for content inside panels, expands, and blockquotes.

    Args:
        lines: List of text lines

    Returns:
        List of ADF block nodes
    """
    nodes = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Blank line — skip
        if not line.strip():
            i += 1
            continue

        # Fenced code block
        fence_match = re.match(r"^(`{3,})([\w+\-]*)$", line.strip())
        if fence_match:
            fence = fence_match.group(1)
            language = fence_match.group(2).strip() or None
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume closing fence
            nodes.append(code_block("\n".join(code_lines), language))
            continue

        # Paragraph — collect consecutive non-block lines
        para_lines = []
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                break
            if line.strip().startswith("```"):
                break
            para_lines.append(line)
            i += 1

        if para_lines:
            text = "\n".join(para_lines)
            nodes.append(paragraph(parse_inline_with_breaks(text)))

    return nodes if nodes else [paragraph([])]


def lines_to_paragraphs(lines: list) -> list:
    """
    Convert a list of text lines (possibly with blank lines between them)
    into a list of ADF paragraph nodes.

    Args:
        lines: List of text lines

    Returns:
        List of ADF paragraph nodes
    """
    paragraphs = []
    current = []

    for line in lines:
        if line.strip() == "":
            if current:
                text = "\n".join(current)
                paragraphs.append(paragraph(parse_inline_with_breaks(text)))
                current = []
        else:
            current.append(line)

    if current:
        text = "\n".join(current)
        paragraphs.append(paragraph(parse_inline_with_breaks(text)))

    return paragraphs if paragraphs else [paragraph([])]


# ---------------------------------------------------------------------------
# Table Parser
# ---------------------------------------------------------------------------


def parse_table(lines: list) -> dict:
    """
    Parse GFM pipe table lines into an ADF table node.

    Args:
        lines: Table lines including header, separator, and data rows

    Returns:
        ADF table node with proper column alignment

    Example:
        lines = [
            "| Left | Center | Right |",
            "|:-----|:------:|------:|",
            "| A    | B      | C     |"
        ]
        table = parse_table(lines)
    """

    def split_row(line):
        """Split table row into cells."""
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    def get_align(sep):
        """Determine alignment from separator cell."""
        s = sep.strip()
        left, right = s.startswith(":"), s.endswith(":")
        if left and right:
            return "center"
        if right:
            return "end"  # ADF schema only allows "center" and "end"
        if left:
            return None  # Left is default, no mark needed
        return None

    header_cells = split_row(lines[0])
    sep_cells = split_row(lines[1])
    alignments = [get_align(s) for s in sep_cells]

    rows = []

    # Header row — always tableHeader cells
    header_row = []
    for i, cell in enumerate(header_cells):
        align = alignments[i] if i < len(alignments) else None
        content = parse_inline(cell)
        if align:
            para = paragraph_with_alignment(content, align)
        else:
            para = paragraph(content)
        header_row.append(table_header([para]))
    rows.append(table_row(header_row))

    # Data rows
    for line in lines[2:]:
        if not line.strip():
            continue
        cells = split_row(line)
        data_row = []
        for i, cell in enumerate(cells):
            align = alignments[i] if i < len(alignments) else None
            content = parse_inline(cell)
            if align:
                para = paragraph_with_alignment(content, align)
            else:
                para = paragraph(content)
            data_row.append(table_cell([para]))
        rows.append(table_row(data_row))

    return table_node(rows)


# ---------------------------------------------------------------------------
# List Parser
# ---------------------------------------------------------------------------


def list_line_info(line: str):
    """
    If line is a list item, return (indent, list_type, task_state, text).

    list_type: "ordered" | "unordered" | "task"
    task_state: "TODO" | "DONE" | None

    Otherwise return None.

    Args:
        line: Single line of text

    Returns:
        Tuple of (indent, list_type, task_state, text) or None
    """
    # Task item: - [ ] or - [x]
    task_match = re.match(r"^( *)([-*+])\s+\[([ xX])\]\s+(.*)", line)
    if task_match:
        indent = len(task_match.group(1))
        state = "DONE" if task_match.group(3).lower() == "x" else "TODO"
        text = task_match.group(4)
        return indent, "task", state, text

    # Regular list item
    m = re.match(r"^( *)([-*+]|\d+\.)\s+(.*)", line)
    if m:
        indent = len(m.group(1))
        is_ordered = bool(re.match(r"\d+\.", m.group(2)))
        list_type = "ordered" if is_ordered else "unordered"
        return indent, list_type, None, m.group(3)

    return None


def build_list(lines: list, base_indent: int = 0):
    """
    Recursively build an ADF list node from a slice of list lines.
    Returns (adf_node, number_of_lines_consumed).

    Supports bulletList, orderedList, and taskList.

    Args:
        lines: List of markdown lines (list items)
        base_indent: Base indentation level

    Returns:
        Tuple of (ADF list node, number of lines consumed)
    """
    items = []
    list_type = None  # "ordered" | "unordered" | "task"
    start_number = 1
    i = 0

    while i < len(lines):
        info = list_line_info(lines[i])
        if info is None:
            break

        indent, item_type, task_state, text = info

        if indent < base_indent:
            break  # returned to a shallower level — stop

        if indent > base_indent:
            i += 1  # deeper line not yet consumed — skip (shouldn't happen)
            continue

        if list_type is None:
            list_type = item_type
            if item_type == "ordered":
                m = re.match(r"^ *(\d+)\.", lines[i])
                start_number = int(m.group(1)) if m else 1

        # Collect child lines that are more indented
        i += 1
        child_lines = []
        while i < len(lines):
            child_info = list_line_info(lines[i])
            if child_info is None:
                break
            if child_info[0] <= indent:  # indent is first element
                break
            child_lines.append(lines[i])
            i += 1

        # Build item content
        if list_type == "task":
            # taskItem contains inline content directly (no paragraph wrapper)
            item_content = parse_inline_with_breaks(text)
            # Nested task lists not supported (taskItem cannot contain taskList)
            # If there are child lines in a task, ignore them for now
            if child_lines:
                print("   ⚠️  Warning: Nested content under task items is not supported - ignoring")
            items.append(task_item(task_state, item_content))
        else:
            # Regular listItem contains paragraphs and can nest other lists
            item_content = [paragraph(parse_inline_with_breaks(text))]
            if child_lines:
                child_indent = child_lines[0].index(child_lines[0].lstrip())
                child_node, _ = build_list(child_lines, base_indent=child_indent)
                item_content.append(child_node)
            items.append(list_item(item_content))

    if not items:
        return bullet_list([]), 0

    # Create appropriate list node
    if list_type == "task":
        node = task_list(items)
    elif list_type == "ordered":
        node = ordered_list(items, start_number)
    else:
        node = bullet_list(items)

    return node, i
