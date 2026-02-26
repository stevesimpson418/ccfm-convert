"""
Main Conversion Logic
=====================
Orchestrates the conversion from CCFM markdown to ADF.

This module contains the main convert() function that ties together
all the node constructors, inline parsing, and block parsing.

Usage:
    from adf import convert

    markdown = "# Hello\\n\\nThis is **bold** text."
    adf_doc = convert(markdown)
"""

import re

from .blocks import build_list, list_line_info, parse_blockquote_block, parse_table
from .inline import parse_inline, parse_inline_with_breaks
from .nodes import code_block, doc, heading, media_single, paragraph, rule


def convert(markdown_text: str) -> dict:
    """
    Convert a CCFM markdown string to an ADF document dict.

    The caller (deploy tool) is responsible for stripping front matter before
    passing the body to this function.

    Args:
        markdown_text: Markdown body string (no front matter)

    Returns:
        ADF document as a Python dict. Serialise with json.dumps() for the API.
    """
    # Strip HTML comments (e.g., markdownlint directives)
    markdown_text = re.sub(r"<!--.*?-->", "", markdown_text, flags=re.DOTALL)

    lines = markdown_text.splitlines()
    content = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- Blank line: skip ---
        if not line.strip():
            i += 1
            continue

        # --- Fenced code block: ```lang ---
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
            content.append(code_block("\n".join(code_lines), language))
            continue

        # --- Heading: # through ###### ---
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            content.append(heading(level, parse_inline(text)))
            i += 1
            continue

        # --- Horizontal rule: ---, ***, ___ ---
        if re.match(r"^(\-{3,}|\*{3,}|_{3,})\s*$", line.strip()):
            content.append(rule())
            i += 1
            continue

        # --- Image: ![alt](url) or ![alt](url){width=VALUE} on its own line ---
        img_match = re.match(
            r"^!\[([^\]]*)\]\(([^)]+)\)(?:\{width=([^}]+)\})?\s*$", line.strip()
        )
        if img_match:
            alt_text = img_match.group(1)
            url = img_match.group(2).strip()
            img_width = img_match.group(3)  # None if no {width=...} attr
            # Strip surrounding quotes (e.g. "file name.png" or 'file name.png')
            if len(url) >= 2 and url[0] in ('"', "'") and url[-1] == url[0]:
                url = url[1:-1]
            content.append(
                media_single(url, alt_text if alt_text else None, width=img_width)
            )
            i += 1
            continue

        # --- Table: current line has | and next line is a separator ---
        if "|" in line:
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(r"^\|?[\s\-:|]+\|", next_line):
                table_lines = []
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                if len(table_lines) >= 2:
                    content.append(parse_table(table_lines))
                continue

        # --- Blockquote / Panel / Expand: lines starting with > ---
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                # ">  text" → strip "> "
                # ">"       → empty paragraph separator
                if lines[i].startswith("> "):
                    quote_lines.append(lines[i][2:])
                else:
                    # bare ">" — blank line within the block
                    quote_lines.append("")
                i += 1
            # Strip trailing blanks
            while quote_lines and quote_lines[-1].strip() == "":
                quote_lines.pop()
            content.append(parse_blockquote_block(quote_lines))
            continue

        # --- Lists: line matches list item pattern ---
        if list_line_info(line):
            list_lines = []
            while i < len(lines):
                if list_line_info(lines[i]):
                    list_lines.append(lines[i])
                    i += 1
                elif list_lines and lines[i].startswith("  "):
                    # Continuation indent (child content)
                    list_lines.append(lines[i])
                    i += 1
                else:
                    break
            node, _ = build_list(list_lines, base_indent=0)
            content.append(node)
            continue

        # --- Paragraph: collect consecutive non-block lines ---
        para_lines = []
        while i < len(lines):
            line = lines[i]
            # Stop conditions for paragraph
            if not line.strip():
                break
            if re.match(r"^#{1,6}\s", line):
                break
            if line.startswith(">"):
                break
            if line.strip().startswith("```"):
                break
            if re.match(r"^(\-{3,}|\*{3,}|_{3,})\s*$", line.strip()):
                break
            if list_line_info(line):
                break
            if "|" in line and i + 1 < len(lines) and re.match(r"^\|?[\s\-:|]+\|", lines[i + 1]):
                break
            para_lines.append(line)
            i += 1

        if para_lines:
            full_text = "\n".join(para_lines)
            inline_nodes = parse_inline_with_breaks(full_text)
            if inline_nodes:
                content.append(paragraph(inline_nodes))

    return doc(content)


# Alias for backwards compatibility
def convert_markdown_to_adf(markdown_text: str) -> dict:
    """Alias for convert(). For backwards compatibility with deploy.py."""
    return convert(markdown_text)
