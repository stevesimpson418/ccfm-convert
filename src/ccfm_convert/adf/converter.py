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

from .blocks import (
    build_list,
    list_line_info,
    parse_blockquote_block,
    parse_table,
)
from .inline import parse_inline, parse_inline_with_breaks
from .nodes import (
    block_card,
    caption_node,
    code_block,
    doc,
    embed_card,
    extension_node,
    heading,
    media_single,
    paragraph,
    rule,
)

# Macros that are always inline (inlineExtension) — never block-level extensions.
# These are excluded from block detection so they fall through to inline parsing.
_INLINE_ONLY_MACROS = {"embed", "date", "anchor"}


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

        # --- Image: ![alt](url) or ![alt](url "caption") or ![alt](url){width=VALUE} ---
        img_match = re.match(r"^!\[([^\]]*)\]\((.+?)\)(?:\{width=([^}]+)\})?\s*$", line.strip())
        if img_match:
            alt_text = img_match.group(1)
            url_part = img_match.group(2).strip()
            img_width = img_match.group(3)  # None if no {width=...} attr
            # Extract optional title/caption: url "caption" or url 'caption'
            caption_text = None
            title_match = re.match(r'^(.+?)\s+(["\'])(.+)\2$', url_part)
            if title_match:
                url = title_match.group(1).strip()
                caption_text = title_match.group(3)
            else:
                url = url_part
            # Strip surrounding quotes from URL (e.g. "file name.png" or 'file name.png')
            if len(url) >= 2 and url[0] in ('"', "'") and url[-1] == url[0]:
                url = url[1:-1]
            cap = None
            if caption_text:
                cap = caption_node(parse_inline(caption_text))
            content.append(
                media_single(
                    url,
                    alt_text if alt_text else None,
                    width=img_width,
                    caption=cap,
                )
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

        # --- Extension macro: @macro or @macro(params) on its own line ---
        # --- Extension macro: @macro or @macro(params) on its own line ---
        macro_match = re.match(r"^@(\w+)(?:\(([^)]*)\))?\s*$", line.strip())
        if macro_match and macro_match.group(1) not in _INLINE_ONLY_MACROS:
            macro_name = macro_match.group(1)
            params_str = macro_match.group(2)
            params = {}
            if params_str:
                if "=" not in params_str:
                    # Simple positional param: anchor uses empty-string key
                    param_key = "" if macro_name == "anchor" else "key"
                    params = {param_key: params_str}
                else:
                    for part in re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', params_str):
                        params[part[0]] = part[1] if part[1] != "" else part[2]
            content.append(extension_node(macro_name, parameters=params if params else None))
            i += 1
            continue

        # --- Embed: @embed(url) on its own line → embedCard ---
        embed_match = re.match(r"^@embed\((.+?)\)\s*$", line.strip())
        if embed_match:
            content.append(embed_card(embed_match.group(1).strip()))
            i += 1
            continue

        # --- Bare URL: standalone URL on its own line → blockCard ---
        bare_url_match = re.match(r"^(https?://\S+)\s*$", line.strip())
        if bare_url_match:
            content.append(block_card(bare_url_match.group(1)))
            i += 1
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
            # Standalone image on its own line
            if re.match(r"^!\[([^\]]*)\]\((.+?)\)(?:\{width=([^}]+)\})?\s*$", line.strip()):
                break
            # @embed(url) on its own line
            if re.match(r"^@embed\(", line.strip()):
                break
            # @macro or @macro(params) on its own line (not inline-only macros)
            macro_stop = re.match(r"^@(\w+)(?:\([^)]*\))?\s*$", line.strip())
            if macro_stop and macro_stop.group(1) not in _INLINE_ONLY_MACROS:
                break
            # Bare URL on its own line (blockCard)
            if re.match(r"^https?://\S+\s*$", line.strip()):
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
