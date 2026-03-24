"""
Inline Parsing
==============
Parses inline markdown syntax (text-level formatting) into ADF inline nodes.

Handles: bold, italic, code, strikethrough, underline, sub/superscript,
links, Confluence page links, emoji, status badges, dates.

Usage:
    from adf.inline import parse_inline

    nodes = parse_inline("**bold** and *italic* text")
"""

import re

from .nodes import (
    date_node,
    emoji_node,
    hard_break,
    inline_card,
    inline_extension_node,
    status_node,
    text_node,
)

# Patterns ordered so that longer/more specific matches win when starting at
# the same position. The parser picks the earliest match overall.
_INLINE_PATTERNS = [
    # Status badge: ::text::color::
    ("status", re.compile(r"::([^:]+)::(\w+)::")),
    # Date token: @date:YYYY-MM-DD
    ("date", re.compile(r"@date:(\d{4}-\d{2}-\d{2})")),
    # Inline extension macro: @macro(params) — e.g., @anchor(section-name)
    ("inline_ext", re.compile(r"@(\w+)\(([^)]+)\)")),
    # Emoji: :shortname:
    ("emoji", re.compile(r":([a-z0-9_+\-]+):")),
    # Confluence page link: [text](<page title>)
    ("page_link", re.compile(r"\[([^\]]+)\]\(<([^>]+)>\)")),
    # External link: [text](url)
    ("link", re.compile(r"\[([^\]]+)\]\(([^)]+)\)")),
    # Inline code: `text` — no further marks inside
    ("code", re.compile(r"`([^`]+)`")),
    # Bold + italic: ***text***
    ("bold_italic", re.compile(r"\*\*\*(.+?)\*\*\*", re.DOTALL)),
    # Bold: **text**
    ("bold", re.compile(r"\*\*(.+?)\*\*", re.DOTALL)),
    # Italic single asterisk: *text*
    ("italic", re.compile(r"\*(.+?)\*", re.DOTALL)),
    # Italic underscore: _text_ (not mid-word)
    ("italic_u", re.compile(r"(?<!\w)_(.+?)_(?!\w)")),
    # Strikethrough: ~~text~~
    ("strike", re.compile(r"~~(.+?)~~", re.DOTALL)),
    # Underline: ++text++
    ("underline", re.compile(r"\+\+(.+?)\+\+", re.DOTALL)),
    # Superscript: ^text^
    ("superscript", re.compile(r"\^(.+?)\^")),
    # Subscript: ~text~ (single tilde, no spaces, distinguished from ~~)
    ("subscript", re.compile(r"(?<!~)~([^\s~]+)~(?!~)")),
]


def _add_mark(nodes: list, mark: dict) -> list:
    """Add a mark to all text nodes in a list of inline nodes."""
    for node in nodes:
        if node["type"] == "text":
            node.setdefault("marks", [])
            node["marks"].append(mark)
    return nodes


def parse_inline(text: str) -> list:
    """
    Parse inline CCFM text into a list of ADF inline nodes.
    Handles all CCFM inline syntax recursively.

    Args:
        text: Plain text string with inline markdown

    Returns:
        List of ADF inline nodes (text with marks, emoji, status, etc.)
    """
    if not text:
        return []

    # Find the earliest-starting match across all patterns
    best_match = None
    best_start = len(text)
    best_type = None

    for pattern_type, pattern in _INLINE_PATTERNS:
        m = pattern.search(text)
        if m and m.start() < best_start:
            best_match = m
            best_start = m.start()
            best_type = pattern_type

    if best_match is None:
        return [text_node(text)]

    nodes = []

    # Text before the match
    if best_start > 0:
        nodes.append(text_node(text[:best_start]))

    m = best_match
    tail = text[m.end() :]

    if best_type == "status":
        nodes.append(status_node(m.group(1).strip(), m.group(2).strip()))

    elif best_type == "date":
        nodes.append(date_node(m.group(1)))

    elif best_type == "emoji":
        nodes.append(emoji_node(m.group(1)))

    elif best_type == "inline_ext":
        macro_name = m.group(1)
        macro_params = m.group(2).strip()
        # @embed is block-level only — emit as plain text when found inline
        if macro_name == "embed":
            nodes.append(text_node(m.group(0)))
        else:
            if "=" not in macro_params:
                # Simple positional param: @macro(value) → {"key": "value"}
                # Anchor macro uses empty-string key: @anchor(name) → {"": "name"}
                param_key = "" if macro_name == "anchor" else "key"
                params = {param_key: macro_params}
            else:
                params = {}
                for part in re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', macro_params):
                    # part[1] is quoted value, part[2] is unquoted — exactly one is non-empty
                    params[part[0]] = part[1] if part[1] != "" else part[2]
            nodes.append(inline_extension_node(macro_name, parameters=params))

    elif best_type == "page_link":
        link_target = m.group(2)
        if link_target.startswith("http://") or link_target.startswith("https://"):
            # External URL in angle brackets → Smart Link card (inlineCard)
            url = link_target
        else:
            # Page title → sentinel URL resolved at deploy time
            url = f"confluence-page://{link_target}"
        nodes.append(inline_card(url))

    elif best_type == "link":
        link_text = m.group(1)
        url = m.group(2)
        inner = parse_inline(link_text)
        nodes.extend(_add_mark(inner, {"type": "link", "attrs": {"href": url}}))

    elif best_type == "code":
        nodes.append(text_node(m.group(1), marks=[{"type": "code"}]))

    elif best_type == "bold_italic":
        inner = parse_inline(m.group(1))
        _add_mark(inner, {"type": "strong"})
        _add_mark(inner, {"type": "em"})
        nodes.extend(inner)

    elif best_type == "bold":
        inner = parse_inline(m.group(1))
        nodes.extend(_add_mark(inner, {"type": "strong"}))

    elif best_type in ("italic", "italic_u"):
        inner = parse_inline(m.group(1))
        nodes.extend(_add_mark(inner, {"type": "em"}))

    elif best_type == "strike":
        inner = parse_inline(m.group(1))
        nodes.extend(_add_mark(inner, {"type": "strike"}))

    elif best_type == "underline":
        inner = parse_inline(m.group(1))
        nodes.extend(_add_mark(inner, {"type": "underline"}))

    elif best_type == "superscript":
        inner = parse_inline(m.group(1))
        nodes.extend(_add_mark(inner, {"type": "subsup", "attrs": {"type": "sup"}}))

    elif best_type == "subscript":
        inner = parse_inline(m.group(1))
        nodes.extend(_add_mark(inner, {"type": "subsup", "attrs": {"type": "sub"}}))

    nodes.extend(parse_inline(tail))
    return nodes


def parse_inline_with_breaks(text: str) -> list:
    """
    Parse inline text, handling hard breaks.
    Trailing backslash or two trailing spaces before a newline → hardBreak node.

    Args:
        text: Text potentially containing hard break markers

    Returns:
        List of ADF inline nodes with hardBreak nodes where appropriate
    """
    # Split on hard break markers: trailing \\ before newline, or 2+ spaces before newline
    segments = re.split(r"\\\n|[ ]{2,}\n", text)
    if len(segments) == 1:
        return parse_inline(text)
    nodes = []
    for i, seg in enumerate(segments):
        nodes.extend(parse_inline(seg))
        if i < len(segments) - 1:
            nodes.append(hard_break())
    return nodes
