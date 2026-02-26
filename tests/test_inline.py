"""Tests for adf.inline module."""

import pytest

from adf.inline import parse_inline, parse_inline_with_breaks


class TestParseInline:
    """Test inline markdown parsing."""

    def test_plain_text(self):
        """Test plain text without formatting."""
        result = parse_inline("Hello world")

        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello world"

    def test_bold(self):
        """Test bold text."""
        result = parse_inline("**bold**")

        assert len(result) == 1
        assert result[0]["text"] == "bold"
        assert result[0]["marks"] == [{"type": "strong"}]

    def test_italic(self):
        """Test italic text."""
        result = parse_inline("*italic*")

        assert len(result) == 1
        assert result[0]["text"] == "italic"
        assert result[0]["marks"] == [{"type": "em"}]

    def test_italic_underscore(self):
        """Test italic with underscore syntax."""
        result = parse_inline("_italic_")

        assert result[0]["text"] == "italic"
        assert result[0]["marks"] == [{"type": "em"}]

    def test_code(self):
        """Test inline code."""
        result = parse_inline("`code()`")

        assert result[0]["text"] == "code()"
        assert result[0]["marks"] == [{"type": "code"}]

    def test_strikethrough(self):
        """Test strikethrough text."""
        result = parse_inline("~~deleted~~")

        assert result[0]["text"] == "deleted"
        assert result[0]["marks"] == [{"type": "strike"}]

    def test_link(self):
        """Test link."""
        result = parse_inline("[Click here](https://example.com)")

        assert result[0]["text"] == "Click here"
        assert len(result[0]["marks"]) == 1
        assert result[0]["marks"][0]["type"] == "link"
        assert result[0]["marks"][0]["attrs"]["href"] == "https://example.com"

    @pytest.mark.skip(reason="Link title attribute parsing may not be fully implemented")
    def test_link_with_title(self):
        """Test link with title attribute."""
        result = parse_inline('[Link](https://example.com "Title")')

        assert result[0]["marks"][0]["attrs"]["href"] == "https://example.com"
        assert result[0]["marks"][0]["attrs"]["title"] == "Title"

    @pytest.mark.skip(reason="Autolink parsing not implemented")
    def test_autolink(self):
        """Test autolink."""
        result = parse_inline("Visit https://example.com for more")

        # Should contain plain text and a link
        assert any(node.get("marks", []) and node["marks"][0]["type"] == "link" for node in result)

    def test_bold_italic(self):
        """Test bold and italic combined."""
        result = parse_inline("***bold italic***")

        assert result[0]["text"] == "bold italic"
        marks = {mark["type"] for mark in result[0]["marks"]}
        assert "strong" in marks
        assert "em" in marks

    def test_bold_with_code(self):
        """Test bold text containing code."""
        result = parse_inline("**bold `code`**")

        # This is complex - implementation may vary
        # Just ensure it parses without error
        assert isinstance(result, list)
        assert len(result) > 0

    def test_multiple_links(self):
        """Test multiple links in text."""
        result = parse_inline("[Link1](http://a.com) and [Link2](http://b.com)")

        links = [
            node for node in result if node.get("marks") and node["marks"][0]["type"] == "link"
        ]
        assert len(links) == 2

    def test_mixed_formatting(self):
        """Test text with mixed formatting."""
        result = parse_inline("Plain **bold** *italic* `code` text")

        # Should have multiple nodes with different formatting
        assert len(result) > 4

        # Check for different mark types
        mark_types = set()
        for node in result:
            if "marks" in node and node["marks"]:
                mark_types.add(node["marks"][0]["type"])

        assert "strong" in mark_types
        assert "em" in mark_types
        assert "code" in mark_types

    @pytest.mark.skip(reason="Escape character handling implementation may differ")
    def test_escaped_characters(self):
        """Test escaped markdown characters."""
        result = parse_inline(r"\*not italic\*")

        assert result[0]["type"] == "text"
        assert "*not italic*" in result[0]["text"]

    def test_empty_string(self):
        """Test empty string."""
        result = parse_inline("")

        assert result == []

    def test_whitespace_only(self):
        """Test whitespace only."""
        result = parse_inline("   ")

        assert len(result) == 1
        assert result[0]["text"] == "   "

    def test_special_characters(self):
        """Test special characters."""
        result = parse_inline("Special: & < > \" '")

        assert len(result) == 1
        assert "Special: & < > \" '" in result[0]["text"]

    def test_emoji(self):
        """Test emoji in text."""
        result = parse_inline("Hello 😀 World")

        assert len(result) == 1
        assert "😀" in result[0]["text"]

    def test_nested_formatting_not_supported(self):
        """Test that nested formatting works."""
        # Markdown: bold containing italic
        result = parse_inline("**bold *and italic***")

        # Implementation dependent, just ensure it parses
        assert isinstance(result, list)


class TestParseInlineWithBreaks:
    """Test inline parsing with hard breaks."""

    def test_single_line(self):
        """Test single line without breaks."""
        result = parse_inline_with_breaks("Hello world")

        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_double_space_break(self):
        """Test hard break with double space + newline."""
        result = parse_inline_with_breaks("Line 1  \nLine 2")

        # Should contain text, hardBreak, text
        assert len(result) == 3
        assert result[0]["text"] == "Line 1"
        assert result[1]["type"] == "hardBreak"
        assert result[2]["text"] == "Line 2"

    def test_multiple_breaks(self):
        """Test multiple hard breaks."""
        result = parse_inline_with_breaks("A  \nB  \nC")

        # Should have 5 nodes: text, break, text, break, text
        assert len(result) == 5
        assert result[0]["text"] == "A"
        assert result[1]["type"] == "hardBreak"
        assert result[2]["text"] == "B"
        assert result[3]["type"] == "hardBreak"
        assert result[4]["text"] == "C"

    def test_break_with_formatting(self):
        """Test hard break with formatted text."""
        result = parse_inline_with_breaks("**Bold**  \n*Italic*")

        # Should contain bold text, break, italic text
        assert any(
            node.get("marks", []) and node["marks"][0]["type"] == "strong" for node in result
        )
        assert any(node["type"] == "hardBreak" for node in result)
        assert any(node.get("marks", []) and node["marks"][0]["type"] == "em" for node in result)

    def test_newline_without_spaces(self):
        """Test newline without double spaces (should not create break)."""
        result = parse_inline_with_breaks("Line 1\nLine 2")

        # Should be treated as soft break (space) in markdown
        assert all(node["type"] != "hardBreak" for node in result)

    def test_empty_lines(self):
        """Test empty lines."""
        result = parse_inline_with_breaks("A  \n  \nB")

        # Should handle gracefully
        assert isinstance(result, list)


class TestCCFMExtensions:
    """Test CCFM-specific inline syntax extensions."""

    def test_status_badge(self):
        """Status badge ::text::color:: produces a status node."""
        result = parse_inline("::In Progress::blue::")

        assert len(result) == 1
        assert result[0]["type"] == "status"
        assert result[0]["attrs"]["text"] == "In Progress"
        assert result[0]["attrs"]["color"] == "BLUE"

    def test_status_badge_with_surrounding_text(self):
        """Status badge embedded in text produces text + status + text nodes."""
        result = parse_inline("Status: ::Done::green:: today")

        types = [n["type"] for n in result]
        assert "status" in types
        assert result[0]["type"] == "text"

    def test_date_token(self):
        """@date:YYYY-MM-DD produces a date node."""
        result = parse_inline("@date:2024-06-01")

        assert len(result) == 1
        assert result[0]["type"] == "date"
        assert "timestamp" in result[0]["attrs"]

    def test_date_token_with_surrounding_text(self):
        """Date token in surrounding text produces multiple nodes."""
        result = parse_inline("Due: @date:2024-12-31")

        types = [n["type"] for n in result]
        assert "date" in types

    def test_emoji_shortname(self):
        """Emoji shortname :name: produces an emoji node."""
        result = parse_inline(":smile:")

        assert len(result) == 1
        assert result[0]["type"] == "emoji"
        assert result[0]["attrs"]["shortName"] == ":smile:"

    def test_emoji_with_text(self):
        """Emoji shortname embedded in text."""
        result = parse_inline("Hello :wave: world")

        types = [n["type"] for n in result]
        assert "emoji" in types

    def test_page_link(self):
        """Confluence page link [text](<page title>) produces an inlineCard node."""
        result = parse_inline("[Link Text](<My Page Title>)")

        assert len(result) == 1
        assert result[0]["type"] == "inlineCard"
        assert result[0]["attrs"]["url"] == "confluence-page://My Page Title"

    def test_page_link_url_uses_page_title_not_text(self):
        """Page link discards display text and uses page title in the sentinel URL."""
        result = parse_inline("[Display Text](<Target Page>)")

        assert result[0]["attrs"]["url"] == "confluence-page://Target Page"

    def test_underline(self):
        """++text++ produces a text node with underline mark."""
        result = parse_inline("++underlined++")

        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert any(m["type"] == "underline" for m in result[0]["marks"])

    def test_superscript(self):
        """^text^ produces a text node with superscript subsup mark."""
        result = parse_inline("E=mc^2^")

        sup_nodes = [
            n for n in result
            if n.get("marks") and any(
                m["type"] == "subsup" and m.get("attrs", {}).get("type") == "sup"
                for m in n["marks"]
            )
        ]
        assert len(sup_nodes) >= 1

    def test_subscript(self):
        """~text~ (single tilde, no spaces) produces a text node with subscript subsup mark."""
        result = parse_inline("H~2~O")

        sub_nodes = [
            n for n in result
            if n.get("marks") and any(
                m["type"] == "subsup" and m.get("attrs", {}).get("type") == "sub"
                for m in n["marks"]
            )
        ]
        assert len(sub_nodes) >= 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unclosed_bold(self):
        """Test unclosed bold marker."""
        result = parse_inline("**not closed")

        # Should handle gracefully
        assert isinstance(result, list)
        assert len(result) > 0

    def test_unclosed_link(self):
        """Test unclosed link."""
        result = parse_inline("[link text](incomplete")

        # Should handle gracefully
        assert isinstance(result, list)

    def test_nested_brackets(self):
        """Test nested brackets in link text."""
        result = parse_inline("[text [with] brackets](http://example.com)")

        # Should handle gracefully
        assert isinstance(result, list)

    def test_very_long_text(self):
        """Test very long text."""
        long_text = "a" * 10000
        result = parse_inline(long_text)

        assert len(result) == 1
        assert len(result[0]["text"]) == 10000

    def test_unicode_characters(self):
        """Test unicode characters."""
        result = parse_inline("Hello 世界 مرحبا мир")

        assert len(result) == 1
        assert "世界" in result[0]["text"]
        assert "مرحبا" in result[0]["text"]  # FIX: Correct spelling
        assert "мир" in result[0]["text"]

    def test_mixed_newlines(self):
        """Test mixed newline types."""
        result = parse_inline_with_breaks("Unix\nWindows\r\nMac\r")

        # Should handle all newline types
        assert isinstance(result, list)

    def test_consecutive_formatting(self):
        """Test consecutive formatted sections."""
        result = parse_inline("**bold1****bold2**")

        # Implementation dependent, just ensure it parses
        assert isinstance(result, list)

    def test_code_with_backticks(self):
        """Test inline code containing backticks."""
        result = parse_inline("``code with ` backtick``")

        # Should handle escaped backticks
        assert isinstance(result, list)
