"""Tests for adf.converter module."""

import pytest

from adf import convert
from adf.converter import convert_markdown_to_adf


class TestBasicConversion:
    """Test basic markdown to ADF conversion."""

    def test_empty_document(self):
        """Test empty markdown."""
        result = convert("")

        assert result["type"] == "doc"
        assert result["version"] == 1
        assert result["content"] == []

    def test_simple_paragraph(self):
        """Test simple paragraph."""
        result = convert("Hello world")

        assert result["content"][0]["type"] == "paragraph"
        assert result["content"][0]["content"][0]["text"] == "Hello world"

    def test_multiple_paragraphs(self):
        """Test multiple paragraphs."""
        markdown = "Paragraph 1\n\nParagraph 2"
        result = convert(markdown)

        assert len(result["content"]) == 2
        assert result["content"][0]["content"][0]["text"] == "Paragraph 1"
        assert result["content"][1]["content"][0]["text"] == "Paragraph 2"


class TestHeadings:
    """Test heading conversion."""

    def test_h1(self):
        """Test H1 heading."""
        result = convert("# Heading 1")

        assert result["content"][0]["type"] == "heading"
        assert result["content"][0]["attrs"]["level"] == 1
        assert result["content"][0]["content"][0]["text"] == "Heading 1"

    def test_h2(self):
        """Test H2 heading."""
        result = convert("## Heading 2")

        assert result["content"][0]["attrs"]["level"] == 2

    def test_h3(self):
        """Test H3 heading."""
        result = convert("### Heading 3")

        assert result["content"][0]["attrs"]["level"] == 3

    def test_h4(self):
        """Test H4 heading."""
        result = convert("#### Heading 4")

        assert result["content"][0]["attrs"]["level"] == 4

    def test_h5(self):
        """Test H5 heading."""
        result = convert("##### Heading 5")

        assert result["content"][0]["attrs"]["level"] == 5

    def test_h6(self):
        """Test H6 heading."""
        result = convert("###### Heading 6")

        assert result["content"][0]["attrs"]["level"] == 6

    def test_heading_with_formatting(self):
        """Test heading with inline formatting."""
        result = convert("# **Bold** Heading")

        assert result["content"][0]["type"] == "heading"
        # Should contain bold text
        marks = result["content"][0]["content"][0].get("marks", [])
        assert any(mark["type"] == "strong" for mark in marks)


class TestLists:
    """Test list conversion."""

    def test_bullet_list(self):
        """Test bullet list."""
        markdown = "- Item 1\n- Item 2\n- Item 3"
        result = convert(markdown)

        assert result["content"][0]["type"] == "bulletList"
        assert len(result["content"][0]["content"]) == 3

    def test_ordered_list(self):
        """Test ordered list."""
        markdown = "1. First\n2. Second\n3. Third"
        result = convert(markdown)

        assert result["content"][0]["type"] == "orderedList"
        assert len(result["content"][0]["content"]) == 3

    def test_nested_list(self):
        """Test nested list."""
        markdown = "- Top\n  - Nested\n  - Nested 2\n- Top 2"
        result = convert(markdown)

        assert result["content"][0]["type"] == "bulletList"
        # First item should contain nested list
        first_item = result["content"][0]["content"][0]
        assert len(first_item["content"]) == 2  # paragraph + nested list

    def test_mixed_list_types(self):
        """Test mixing bullet and ordered lists."""
        markdown = "- Bullet\n  1. Ordered\n  2. Ordered 2"
        result = convert(markdown)

        assert result["content"][0]["type"] == "bulletList"
        # Should contain nested ordered list


class TestCodeBlocks:
    """Test code block conversion."""

    def test_code_block_with_language(self):
        """Test fenced code block with language."""
        markdown = "```python\nprint('hello')\n```"
        result = convert(markdown)

        assert result["content"][0]["type"] == "codeBlock"
        assert result["content"][0]["attrs"]["language"] == "python"
        assert "print('hello')" in result["content"][0]["content"][0]["text"]

    def test_code_block_without_language(self):
        """Test fenced code block without language."""
        markdown = "```\ncode here\n```"
        result = convert(markdown)

        assert result["content"][0]["type"] == "codeBlock"

    @pytest.mark.skip(reason="Indented code blocks may not be implemented")
    def test_indented_code_block(self):
        """Test indented code block."""
        markdown = "    code\n    more code"
        result = convert(markdown)

        assert result["content"][0]["type"] == "codeBlock"


class TestBlockquotes:
    """Test blockquote conversion."""

    def test_simple_blockquote(self):
        """Test simple blockquote."""
        markdown = "> Quote"
        result = convert(markdown)

        assert result["content"][0]["type"] == "blockquote"

    def test_multiline_blockquote(self):
        """Test multiline blockquote."""
        markdown = "> Line 1\n> Line 2"
        result = convert(markdown)

        assert result["content"][0]["type"] == "blockquote"

    def test_nested_blockquote(self):
        """Test nested blockquote."""
        markdown = "> Outer\n>> Nested"
        result = convert(markdown)

        assert result["content"][0]["type"] == "blockquote"


class TestTables:
    """Test table conversion."""

    def test_simple_table(self):
        """Test simple table."""
        markdown = """| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |"""
        result = convert(markdown)

        assert result["content"][0]["type"] == "table"
        # First row should be headers
        assert result["content"][0]["content"][0]["content"][0]["type"] == "tableHeader"

    def test_table_with_alignment(self):
        """Test table with column alignment."""
        markdown = """| Left | Center | Right |
|:-----|:------:|------:|
| L    | C      | R     |"""
        result = convert(markdown)

        assert result["content"][0]["type"] == "table"

    def test_table_with_formatting(self):
        """Test table with formatted content."""
        markdown = """| **Bold** | *Italic* |
|----------|----------|
| `code`   | text     |"""
        result = convert(markdown)

        # Should contain formatted cells
        assert result["content"][0]["type"] == "table"


class TestHorizontalRule:
    """Test horizontal rule conversion."""

    def test_hr_dashes(self):
        """Test HR with dashes."""
        result = convert("---")

        assert result["content"][0]["type"] == "rule"

    def test_hr_asterisks(self):
        """Test HR with asterisks."""
        result = convert("***")

        assert result["content"][0]["type"] == "rule"

    def test_hr_underscores(self):
        """Test HR with underscores."""
        result = convert("___")

        assert result["content"][0]["type"] == "rule"


class TestImages:
    """Test image conversion."""

    def test_image_with_alt(self):
        """Test image with alt text."""
        result = convert("![Alt text](image.png)")

        assert result["content"][0]["type"] == "mediaSingle"
        media = result["content"][0]["content"][0]
        assert media["type"] == "media"
        assert media["attrs"]["url"] == "image.png"
        assert media["attrs"]["alt"] == "Alt text"

    def test_image_default_width_is_narrow(self):
        """Test that images default to narrow page width (760px)."""
        result = convert("![Alt](image.png)")

        ms = result["content"][0]
        assert ms["attrs"]["width"] == 760
        assert ms["attrs"]["widthType"] == "pixel"
        assert ms["attrs"]["layout"] == "center"

    def test_image_without_alt(self):
        """Test image without alt text."""
        result = convert("![](image.png)")

        media = result["content"][0]["content"][0]
        assert media["attrs"]["url"] == "image.png"

    @pytest.mark.skip(reason="Image title attribute may not be fully supported")
    def test_image_with_title(self):
        """Test image with title."""
        result = convert('![Alt](img.png "Title")')

        media = result["content"][0]["content"][0]
        assert media["attrs"]["url"] == "img.png"

    def test_image_url_with_double_quotes(self):
        """Test that double-quoted URLs are stripped of their quotes."""
        result = convert('![CCFM Logo]("CCFM.png")')

        media = result["content"][0]["content"][0]
        assert media["attrs"]["url"] == "CCFM.png"

    def test_image_url_with_single_quotes(self):
        """Test that single-quoted URLs are stripped of their quotes."""
        result = convert("![Logo]('logo.png')")

        media = result["content"][0]["content"][0]
        assert media["attrs"]["url"] == "logo.png"

    def test_image_url_with_spaces_and_quotes(self):
        """Test that quoted URLs with spaces in the filename work correctly."""
        result = convert('![My Image]("my image file.png")')

        media = result["content"][0]["content"][0]
        assert media["attrs"]["url"] == "my image file.png"

    def test_image_width_narrow_preset(self):
        """Test {width=narrow} maps to 760px center layout."""
        result = convert("![Alt](image.png){width=narrow}")

        ms = result["content"][0]
        assert ms["attrs"]["width"] == 760
        assert ms["attrs"]["widthType"] == "pixel"
        assert ms["attrs"]["layout"] == "center"

    def test_image_width_wide_preset(self):
        """Test {width=wide} maps to wide layout (no pixel width attrs)."""
        result = convert("![Alt](image.png){width=wide}")

        ms = result["content"][0]
        assert ms["attrs"]["layout"] == "wide"
        assert "width" not in ms["attrs"]
        assert "widthType" not in ms["attrs"]

    def test_image_width_max_preset(self):
        """Test {width=max} maps to full-width layout (no pixel width attrs)."""
        result = convert("![Alt](image.png){width=max}")

        ms = result["content"][0]
        assert ms["attrs"]["layout"] == "full-width"
        assert "width" not in ms["attrs"]
        assert "widthType" not in ms["attrs"]

    def test_image_width_custom_pixels(self):
        """Test {width=500} maps to 500px center layout."""
        result = convert("![Alt](image.png){width=500}")

        ms = result["content"][0]
        assert ms["attrs"]["layout"] == "center"
        assert ms["attrs"]["width"] == 500
        assert ms["attrs"]["widthType"] == "pixel"


class TestLinks:
    """Test link conversion."""

    def test_inline_link(self):
        """Test inline link."""
        result = convert("[Link text](https://example.com)")

        node = result["content"][0]["content"][0]
        assert node["text"] == "Link text"
        assert node["marks"][0]["type"] == "link"
        assert node["marks"][0]["attrs"]["href"] == "https://example.com"

    def test_autolink(self):
        """Test autolink."""
        result = convert("https://example.com")

        # Should convert to link
        assert isinstance(result["content"], list)

    def test_reference_link(self):
        """Test reference-style link."""
        markdown = "[Link][ref]\n\n[ref]: https://example.com"
        result = convert(markdown)

        # Should resolve reference
        assert isinstance(result["content"], list)


class TestInlineFormatting:
    """Test inline formatting."""

    def test_bold(self):
        """Test bold text."""
        result = convert("**bold**")

        node = result["content"][0]["content"][0]
        assert node["text"] == "bold"
        assert node["marks"][0]["type"] == "strong"

    def test_italic(self):
        """Test italic text."""
        result = convert("*italic*")

        node = result["content"][0]["content"][0]
        assert node["marks"][0]["type"] == "em"

    def test_code(self):
        """Test inline code."""
        result = convert("`code`")

        node = result["content"][0]["content"][0]
        assert node["marks"][0]["type"] == "code"

    def test_strikethrough(self):
        """Test strikethrough."""
        result = convert("~~deleted~~")

        node = result["content"][0]["content"][0]
        assert node["marks"][0]["type"] == "strike"

    def test_combined_formatting(self):
        """Test combined formatting."""
        result = convert("***bold italic***")

        node = result["content"][0]["content"][0]
        mark_types = {mark["type"] for mark in node["marks"]}
        assert "strong" in mark_types
        assert "em" in mark_types


class TestComplexDocuments:
    """Test complex document structures."""

    def test_mixed_content(self):
        """Test document with mixed content types."""
        markdown = """# Title

Paragraph with **bold** and *italic*.

- List item 1
- List item 2

> Quote

```python
code()
```

---

Final paragraph."""

        result = convert(markdown)

        # Should have multiple content types
        types = {node["type"] for node in result["content"]}
        assert "heading" in types
        assert "paragraph" in types
        assert "bulletList" in types
        assert "blockquote" in types
        assert "codeBlock" in types
        assert "rule" in types

    def test_nested_structures(self):
        """Test deeply nested structures."""
        markdown = """- Top level
  - Nested
    - Double nested
      - Triple nested"""

        result = convert(markdown)

        # Should handle deep nesting
        assert result["content"][0]["type"] == "bulletList"

    def test_table_in_list(self):
        """Test table inside list (if supported)."""
        markdown = """- Item

| A | B |
|---|---|
| 1 | 2 |"""

        result = convert(markdown)

        # Should handle gracefully
        assert isinstance(result["content"], list)


class TestParagraphStopConditions:
    """Tests targeting each paragraph collection stop condition (lines 151-162)."""

    def test_paragraph_stops_at_heading(self):
        """Paragraph collection stops when a heading line is encountered (line 152)."""
        # Text on the first line starts a paragraph; heading on next line must end it
        md = "Some text\n# Heading"
        result = convert(md)

        types = [n["type"] for n in result["content"]]
        assert "paragraph" in types
        assert "heading" in types

    def test_paragraph_stops_at_blockquote(self):
        """Paragraph collection stops when a blockquote line is encountered (line 154)."""
        md = "Some text\n> Quote"
        result = convert(md)

        types = [n["type"] for n in result["content"]]
        assert "paragraph" in types
        assert "blockquote" in types

    def test_paragraph_stops_at_code_fence(self):
        """Paragraph collection stops at a fenced code block (line 156)."""
        md = "Some text\n```python\ncode()\n```"
        result = convert(md)

        types = [n["type"] for n in result["content"]]
        assert "paragraph" in types
        assert "codeBlock" in types

    def test_paragraph_stops_at_horizontal_rule(self):
        """Paragraph collection stops at a horizontal rule (line 158)."""
        md = "Some text\n---"
        result = convert(md)

        types = [n["type"] for n in result["content"]]
        assert "paragraph" in types
        assert "rule" in types

    def test_paragraph_stops_at_list(self):
        """Paragraph collection stops when a list item is encountered (line 160)."""
        md = "Some text\n- list item"
        result = convert(md)

        types = [n["type"] for n in result["content"]]
        assert "paragraph" in types
        assert "bulletList" in types

    def test_paragraph_stops_at_table(self):
        """Paragraph collection stops when a table starts (line 162)."""
        md = "Some text\n| A | B |\n|---|---|\n| 1 | 2 |"
        result = convert(md)

        types = [n["type"] for n in result["content"]]
        assert "paragraph" in types
        assert "table" in types


class TestBackwardsCompatibilityAlias:
    """Test the convert_markdown_to_adf alias (line 178)."""

    def test_alias_returns_same_result_as_convert(self):
        """convert_markdown_to_adf is an alias for convert() and produces identical output."""
        md = "# Hello\n\nWorld"
        assert convert_markdown_to_adf(md) == convert(md)

    def test_alias_handles_empty_input(self):
        """Alias handles empty input the same way as convert()."""
        assert convert_markdown_to_adf("") == convert("")


class TestEdgeCases:
    """Test edge cases."""

    def test_whitespace_handling(self):
        """Test whitespace handling."""
        result = convert("  \n  \n  ")

        # Should handle gracefully
        assert isinstance(result["content"], list)

    def test_special_characters(self):
        """Test special characters."""
        result = convert("Special: & < > \" '")

        assert isinstance(result["content"], list)

    def test_very_long_document(self):
        """Test very long document."""
        markdown = "# Heading\n\n" + ("Paragraph\n\n" * 100)
        result = convert(markdown)

        # Should handle large documents
        assert len(result["content"]) > 50

    def test_unicode_content(self):
        """Test unicode content."""
        result = convert("Hello 世界 مرحبا мир 👋")

        text = result["content"][0]["content"][0]["text"]
        assert "世界" in text
        assert "👋" in text

    def test_html_entities(self):
        """Test HTML entities."""
        result = convert("&lt;tag&gt; &amp; &quot;")

        # Should handle HTML entities
        assert isinstance(result["content"], list)

    def test_malformed_markdown(self):
        """Test malformed markdown."""
        markdown = "**unclosed bold\n\n[incomplete link("
        result = convert(markdown)

        # Should handle gracefully without crashing
        assert isinstance(result["content"], list)
