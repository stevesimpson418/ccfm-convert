"""Tests for ADF-to-Markdown reverse converter."""

import pytest

from ccfm_convert.adf.converter import convert
from ccfm_convert.adf.reverse import adf_to_markdown


def _doc(*content):
    """Helper: wrap content nodes in an ADF document."""
    return {"version": 1, "type": "doc", "content": list(content)}


def _paragraph(*content):
    return {"type": "paragraph", "content": list(content)}


def _text(text, marks=None):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _heading(level, *content):
    return {"type": "heading", "attrs": {"level": level}, "content": list(content)}


def _ordered_list(*items, order=1):
    node = {"type": "orderedList", "content": list(items)}
    if order != 1:
        node["attrs"] = {"order": order}
    return node


def _list_item(*content):
    return {"type": "listItem", "content": list(content)}


def _hard_break():
    return {"type": "hardBreak"}


# ── Plain paragraph ──────────────────────────────────────────────────


class TestPlainParagraph:
    def test_single_paragraph(self):
        adf = _doc(_paragraph(_text("Hello world")))
        assert adf_to_markdown(adf) == "Hello world\n"

    def test_multiple_text_nodes_in_paragraph(self):
        adf = _doc(_paragraph(_text("Hello "), _text("world")))
        assert adf_to_markdown(adf) == "Hello world\n"

    def test_two_paragraphs_separated_by_blank_line(self):
        adf = _doc(
            _paragraph(_text("First")),
            _paragraph(_text("Second")),
        )
        assert adf_to_markdown(adf) == "First\n\nSecond\n"

    def test_paragraph_with_empty_content(self):
        adf = _doc({"type": "paragraph", "content": []})
        assert adf_to_markdown(adf) == "\n"

    def test_paragraph_with_missing_content_key(self):
        adf = _doc({"type": "paragraph"})
        assert adf_to_markdown(adf) == "\n"


# ── Headings ─────────────────────────────────────────────────────────


class TestHeadings:
    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_heading_levels(self, level):
        adf = _doc(_heading(level, _text("Title")))
        expected = "#" * level + " Title\n"
        assert adf_to_markdown(adf) == expected

    def test_heading_with_bold(self):
        adf = _doc(_heading(2, _text("bold", marks=[{"type": "strong"}]), _text(" text")))
        assert adf_to_markdown(adf) == "## **bold** text\n"

    def test_heading_then_paragraph(self):
        adf = _doc(
            _heading(1, _text("Title")),
            _paragraph(_text("Body text")),
        )
        assert adf_to_markdown(adf) == "# Title\n\nBody text\n"


# ── Inline marks ─────────────────────────────────────────────────────


class TestInlineMarks:
    def test_bold(self):
        adf = _doc(_paragraph(_text("bold", marks=[{"type": "strong"}])))
        assert adf_to_markdown(adf) == "**bold**\n"

    def test_italic(self):
        adf = _doc(_paragraph(_text("italic", marks=[{"type": "em"}])))
        assert adf_to_markdown(adf) == "*italic*\n"

    def test_bold_italic(self):
        adf = _doc(_paragraph(_text("both", marks=[{"type": "strong"}, {"type": "em"}])))
        assert adf_to_markdown(adf) == "***both***\n"

    def test_strikethrough(self):
        adf = _doc(_paragraph(_text("struck", marks=[{"type": "strike"}])))
        assert adf_to_markdown(adf) == "~~struck~~\n"

    def test_inline_code(self):
        adf = _doc(_paragraph(_text("code", marks=[{"type": "code"}])))
        assert adf_to_markdown(adf) == "`code`\n"

    def test_underline(self):
        adf = _doc(_paragraph(_text("underlined", marks=[{"type": "underline"}])))
        assert adf_to_markdown(adf) == "++underlined++\n"

    def test_superscript(self):
        adf = _doc(_paragraph(_text("sup", marks=[{"type": "subsup", "attrs": {"type": "sup"}}])))
        assert adf_to_markdown(adf) == "^sup^\n"

    def test_subscript(self):
        adf = _doc(_paragraph(_text("sub", marks=[{"type": "subsup", "attrs": {"type": "sub"}}])))
        assert adf_to_markdown(adf) == "~sub~\n"

    def test_link(self):
        adf = _doc(
            _paragraph(
                _text(
                    "click here",
                    marks=[{"type": "link", "attrs": {"href": "https://example.com"}}],
                )
            )
        )
        assert adf_to_markdown(adf) == "[click here](https://example.com)\n"

    def test_bold_inside_link(self):
        adf = _doc(
            _paragraph(
                _text(
                    "bold link",
                    marks=[
                        {"type": "link", "attrs": {"href": "https://example.com"}},
                        {"type": "strong"},
                    ],
                )
            )
        )
        assert adf_to_markdown(adf) == "[**bold link**](https://example.com)\n"

    def test_empty_marks_list(self):
        adf = _doc(_paragraph(_text("plain", marks=[])))
        assert adf_to_markdown(adf) == "plain\n"

    def test_mixed_plain_and_marked_text(self):
        adf = _doc(
            _paragraph(
                _text("Hello "),
                _text("bold", marks=[{"type": "strong"}]),
                _text(" world"),
            )
        )
        assert adf_to_markdown(adf) == "Hello **bold** world\n"


# ── Hard break ───────────────────────────────────────────────────────


class TestHardBreak:
    def test_hard_break_in_paragraph(self):
        adf = _doc(_paragraph(_text("first"), _hard_break(), _text("second")))
        assert adf_to_markdown(adf) == "first\\\nsecond\n"

    def test_hard_break_at_end_of_paragraph(self):
        adf = _doc(_paragraph(_text("text"), _hard_break()))
        assert adf_to_markdown(adf) == "text\\\n\n"


# ── Ordered list ─────────────────────────────────────────────────────


class TestOrderedList:
    def test_simple_ordered_list(self):
        adf = _doc(
            _ordered_list(
                _list_item(_paragraph(_text("first"))),
                _list_item(_paragraph(_text("second"))),
                _list_item(_paragraph(_text("third"))),
            )
        )
        expected = "1. first\n2. second\n3. third\n"
        assert adf_to_markdown(adf) == expected

    def test_ordered_list_custom_start(self):
        adf = _doc(
            _ordered_list(
                _list_item(_paragraph(_text("alpha"))),
                _list_item(_paragraph(_text("beta"))),
                order=3,
            )
        )
        expected = "3. alpha\n4. beta\n"
        assert adf_to_markdown(adf) == expected

    def test_ordered_list_with_marks(self):
        adf = _doc(
            _ordered_list(
                _list_item(_paragraph(_text("bold", marks=[{"type": "strong"}]))),
            )
        )
        assert adf_to_markdown(adf) == "1. **bold**\n"

    def test_ordered_list_empty_item(self):
        adf = _doc(
            _ordered_list(
                _list_item(_paragraph()),
            )
        )
        assert adf_to_markdown(adf) == "1. \n"

    def test_ordered_list_item_with_no_content(self):
        """listItem with completely missing content key."""
        adf = _doc(
            _ordered_list(
                {"type": "listItem"},
            )
        )
        assert adf_to_markdown(adf) == "1. \n"


# ── Unknown nodes ────────────────────────────────────────────────────


class TestUnknownNodes:
    def test_unknown_node_skipped(self):
        adf = _doc(
            _paragraph(_text("before")),
            {"type": "codeBlock", "content": [{"type": "text", "text": "x = 1"}]},
            _paragraph(_text("after")),
        )
        assert adf_to_markdown(adf) == "before\n\nafter\n"

    def test_empty_document(self):
        adf = _doc()
        assert adf_to_markdown(adf) == ""

    def test_document_with_only_unknown_nodes(self):
        adf = _doc({"type": "rule"}, {"type": "table"})
        assert adf_to_markdown(adf) == ""


# ── Mixed document ───────────────────────────────────────────────────


class TestMixedDocument:
    def test_heading_paragraph_list(self):
        adf = _doc(
            _heading(1, _text("Shopping")),
            _paragraph(_text("Buy these items:")),
            _ordered_list(
                _list_item(_paragraph(_text("Milk"))),
                _list_item(_paragraph(_text("Eggs"))),
                _list_item(_paragraph(_text("Bread"))),
            ),
        )
        expected = (
            "# Shopping\n" "\n" "Buy these items:\n" "\n" "1. Milk\n" "2. Eggs\n" "3. Bread\n"
        )
        assert adf_to_markdown(adf) == expected

    def test_multiple_headings_with_paragraphs(self):
        adf = _doc(
            _heading(1, _text("Main")),
            _paragraph(_text("Intro")),
            _heading(2, _text("Sub")),
            _paragraph(_text("Detail")),
        )
        expected = "# Main\n\nIntro\n\n## Sub\n\nDetail\n"
        assert adf_to_markdown(adf) == expected


# ── Round-trip fidelity ──────────────────────────────────────────────


class TestRoundTrip:
    """Verify: markdown → convert() → adf_to_markdown() → convert() produces same ADF."""

    def test_round_trip_heading_and_paragraph(self):
        markdown = "# Hello World\n\nThis is **bold** and *italic* text.\n"
        adf = convert(markdown)
        regenerated_md = adf_to_markdown(adf)
        re_adf = convert(regenerated_md)
        assert re_adf == adf

    def test_round_trip_ordered_list(self):
        markdown = "1. First item\n2. Second item\n3. Third item\n"
        adf = convert(markdown)
        regenerated_md = adf_to_markdown(adf)
        re_adf = convert(regenerated_md)
        assert re_adf == adf

    def test_round_trip_mixed(self):
        markdown = "# Title\n\nSome text here.\n\n1. One\n2. Two\n"
        adf = convert(markdown)
        regenerated_md = adf_to_markdown(adf)
        re_adf = convert(regenerated_md)
        assert re_adf == adf

    def test_round_trip_inline_marks(self):
        markdown = "This has **bold**, *italic*, and ~~strikethrough~~ text.\n"
        adf = convert(markdown)
        regenerated_md = adf_to_markdown(adf)
        re_adf = convert(regenerated_md)
        assert re_adf == adf

    def test_round_trip_link(self):
        markdown = "Visit [Example](https://example.com) for more.\n"
        adf = convert(markdown)
        regenerated_md = adf_to_markdown(adf)
        re_adf = convert(regenerated_md)
        assert re_adf == adf
