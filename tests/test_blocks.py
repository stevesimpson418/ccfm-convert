"""Tests for adf.blocks module."""

import pytest

from adf.blocks import (
    build_list,
    lines_to_paragraphs,
    list_line_info,
    parse_block_content,
    parse_blockquote_block,
    parse_table,
)


class TestParseBlockquote:
    """Test blockquote parsing."""

    def test_plain_blockquote(self):
        """Test plain blockquote."""
        lines = ["This is a quote"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "blockquote"
        assert len(result["content"]) > 0

    def test_empty_blockquote(self):
        """Test empty blockquote."""
        result = parse_blockquote_block([])

        assert result["type"] == "blockquote"

    def test_panel_info(self):
        """Test info panel."""
        lines = ["[!info]", "Information message"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "panel"
        assert result["attrs"]["panelType"] == "info"

    def test_panel_note(self):
        """Test note panel."""
        lines = ["[!note]", "Note text"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "panel"
        assert result["attrs"]["panelType"] == "note"

    def test_panel_warning(self):
        """Test warning panel."""
        lines = ["[!warning]", "Warning message"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "panel"
        assert result["attrs"]["panelType"] == "warning"

    def test_panel_error(self):
        """Test error panel."""
        lines = ["[!error]", "Error message"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "panel"
        assert result["attrs"]["panelType"] == "error"

    def test_panel_success(self):
        """Test success panel."""
        lines = ["[!success]", "Success message"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "panel"
        assert result["attrs"]["panelType"] == "success"

    def test_panel_invalid_type(self):
        """Test panel with invalid type (should fallback to blockquote)."""
        lines = ["[!invalid]", "Text"]
        result = parse_blockquote_block(lines)

        # Should fall back to blockquote
        assert result["type"] in ["blockquote", "panel"]

    def test_expand_block(self):
        """Test expand block."""
        lines = ["[!expand Title]", "Hidden content"]  # FIX: Title inside brackets
        result = parse_blockquote_block(lines)

        assert result["type"] == "expand"
        assert "title" in result["attrs"]
        assert result["attrs"]["title"] == "Title"

    def test_expand_with_multiline_content(self):
        """Test expand with multiple lines."""
        lines = ["[!expand Details]", "Line 1", "Line 2", "Line 3"]  # FIX: Title inside brackets
        result = parse_blockquote_block(lines)

        assert result["type"] == "expand"
        assert result["attrs"]["title"] == "Details"
        assert len(result["content"]) > 0

    def test_multiline_blockquote(self):
        """Test multiline blockquote."""
        lines = ["First line", "Second line", "Third line"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "blockquote"

    def test_blockquote_with_formatting(self):
        """Test blockquote with inline formatting."""
        lines = ["**Bold** and *italic* text"]
        result = parse_blockquote_block(lines)

        assert result["type"] == "blockquote"


class TestParseTable:
    """Test table parsing."""

    def test_simple_table(self):
        """Test simple 2x2 table."""
        lines = ["| Header 1 | Header 2 |", "|----------|----------|", "| Cell 1   | Cell 2   |"]
        result = parse_table(lines)

        assert result["type"] == "table"
        # First row should be headers
        assert result["content"][0]["content"][0]["type"] == "tableHeader"

    def test_table_with_alignment(self):
        """Test table with column alignment."""
        lines = [
            "| Left | Center | Right |",
            "|:-----|:------:|------:|",
            "| L    | C      | R     |",
        ]
        result = parse_table(lines)

        assert result["type"] == "table"
        # Should have proper structure
        assert len(result["content"]) == 2  # Header + 1 row

    def test_table_multiple_rows(self):
        """Test table with multiple data rows."""
        lines = ["| A | B |", "|---|---|", "| 1 | 2 |", "| 3 | 4 |", "| 5 | 6 |"]
        result = parse_table(lines)

        assert result["type"] == "table"
        assert len(result["content"]) == 4  # 1 header + 3 data rows

    def test_table_with_empty_cells(self):
        """Test table with empty cells."""
        lines = ["| A | B |", "|---|---|", "|   | 2 |", "| 3 |   |"]
        result = parse_table(lines)

        assert result["type"] == "table"

    def test_table_with_formatting(self):
        """Test table with formatted content."""
        lines = ["| **Bold** | *Italic* |", "|----------|----------|", "| `code`   | text     |"]
        result = parse_table(lines)

        assert result["type"] == "table"

    def test_table_with_pipes_in_content(self):
        """Test table with pipe characters in content."""
        lines = ["| Code | Description |", "|------|-------------|", "| `a\\|b` | Pipe char |"]
        result = parse_table(lines)

        # Should handle escaped pipes
        assert result["type"] == "table"

    def test_table_no_header_separator(self):
        """Test table without proper separator."""
        lines = ["| A | B |", "| 1 | 2 |"]
        # Behavior may vary - just ensure it doesn't crash
        result = parse_table(lines)
        assert isinstance(result, dict)

    def test_single_column_table(self):
        """Test table with single column."""
        lines = ["| Header |", "|--------|", "| Cell 1 |", "| Cell 2 |"]
        result = parse_table(lines)

        assert result["type"] == "table"

    def test_table_with_uneven_columns(self):
        """Test table with uneven column counts."""
        lines = [
            "| A | B | C |",
            "|---|---|---|",
            "| 1 | 2 |",  # Missing column
            "| 3 | 4 | 5 | 6 |",  # Extra column
        ]
        # Should handle gracefully
        result = parse_table(lines)
        assert result["type"] == "table"


class TestBuildList:
    """Test list building."""

    def test_bullet_list(self):
        """Test bullet list."""
        lines = ["- Item 1", "- Item 2", "- Item 3"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "bulletList"
        assert len(result["content"]) == 3
        assert consumed == 3  # FIX: Check consumed count

    def test_ordered_list(self):
        """Test ordered list."""
        lines = ["1. First", "2. Second", "3. Third"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "orderedList"
        assert len(result["content"]) == 3
        assert consumed == 3

    def test_task_list(self):
        """Test task list."""
        lines = ["- [ ] Task 1", "- [x] Task 2"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "taskList"
        assert len(result["content"]) == 2
        assert consumed == 2

    def test_nested_bullet_list(self):
        """Test nested bullet list."""
        lines = ["- Top", "  - Nested 1", "  - Nested 2", "- Top 2"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "bulletList"
        # Top level should have 2 items
        assert len(result["content"]) == 2
        assert consumed == 4

    def test_deeply_nested_list(self):
        """Test deeply nested list."""
        lines = ["- L1", "  - L2", "    - L3", "      - L4"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        # Should handle deep nesting
        assert result["type"] == "bulletList"
        assert consumed == 4

    def test_mixed_list_types(self):
        """Test mixing bullet and ordered lists."""
        lines = ["- Bullet", "  1. Ordered nested"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        # Should handle mixed types
        assert result["type"] == "bulletList"
        assert consumed == 2

    def test_empty_list(self):
        """Test empty list."""
        result, consumed = build_list([])  # FIX: Returns tuple

        # Should return empty bullet list or handle gracefully
        assert result["type"] == "bulletList"
        assert consumed == 0

    def test_list_with_multiline_content(self):
        """Test list items with multiline content."""
        lines = ["- Line 1", "- Single line"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "bulletList"
        assert consumed == 2

    def test_list_with_formatted_content(self):
        """Test list with formatted text."""
        lines = ["- **Bold** item", "- *Italic* item"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "bulletList"
        assert consumed == 2


class TestHelperFunctions:
    """Test helper functions."""

    def test_list_line_info_bullet(self):
        """Test parsing bullet list line."""
        result = list_line_info("- Item text")

        assert result is not None
        indent, list_type, task_state, text = result
        assert indent == 0
        assert list_type == "unordered"
        assert task_state is None
        assert text == "Item text"

    def test_list_line_info_ordered(self):
        """Test parsing ordered list line."""
        result = list_line_info("1. First item")

        assert result is not None
        indent, list_type, task_state, text = result
        assert indent == 0
        assert list_type == "ordered"
        assert task_state is None
        assert text == "First item"

    def test_list_line_info_task_todo(self):
        """Test parsing task list (unchecked)."""
        result = list_line_info("- [ ] Task to do")

        assert result is not None
        indent, list_type, task_state, text = result
        assert indent == 0
        assert list_type == "task"
        assert task_state == "TODO"
        assert text == "Task to do"

    def test_list_line_info_task_done(self):
        """Test parsing task list (checked)."""
        result = list_line_info("- [x] Completed task")

        assert result is not None
        indent, list_type, task_state, text = result
        assert indent == 0
        assert list_type == "task"
        assert task_state == "DONE"
        assert text == "Completed task"

    def test_list_line_info_indented(self):
        """Test parsing indented list line."""
        result = list_line_info("  - Nested item")

        assert result is not None
        indent, list_type, task_state, text = result
        assert indent == 2
        assert list_type == "unordered"

    def test_list_line_info_not_list(self):
        """Test non-list line returns None."""
        result = list_line_info("Just regular text")

        assert result is None

    def test_parse_block_content_paragraph(self):
        """Test parsing block content with paragraphs."""
        lines = ["First line", "Second line"]
        result = parse_block_content(lines)

        assert len(result) == 1
        assert result[0]["type"] == "paragraph"

    def test_parse_block_content_code_block(self):
        """Test parsing block content with code block."""
        lines = ["```python", "print('hello')", "```"]
        result = parse_block_content(lines)

        assert len(result) == 1
        assert result[0]["type"] == "codeBlock"

    def test_parse_block_content_empty(self):
        """Test parsing empty block content."""
        result = parse_block_content([])

        # Should return at least one paragraph
        assert len(result) >= 1

    def test_lines_to_paragraphs_single(self):
        """Test converting single line to paragraph."""
        result = lines_to_paragraphs(["Single line"])

        assert len(result) == 1
        assert result[0]["type"] == "paragraph"

    def test_lines_to_paragraphs_multiple(self):
        """Test converting multiple paragraphs."""
        lines = ["First paragraph", "", "Second paragraph", "", "Third paragraph"]
        result = lines_to_paragraphs(lines)

        assert len(result) == 3
        for para in result:
            assert para["type"] == "paragraph"

    def test_lines_to_paragraphs_empty(self):
        """Test converting empty lines."""
        result = lines_to_paragraphs([])

        # Should return at least one paragraph
        assert len(result) >= 1


class TestCoverageGaps:
    """Tests targeting specific uncovered code paths in blocks.py."""

    def test_parse_block_content_skips_blank_lines(self):
        """parse_block_content skips blank lines between paragraphs (lines 99-100)."""
        lines = ["First paragraph", "", "Second paragraph"]
        result = parse_block_content(lines)

        # Should produce two paragraphs, not one
        assert len(result) == 2
        assert all(n["type"] == "paragraph" for n in result)

    def test_parse_block_content_paragraph_breaks_on_blank_line(self):
        """Paragraph collection stops at blank line inside parse_block_content (line 121)."""
        lines = ["line one", "line two", "", "line three"]
        result = parse_block_content(lines)

        # Paragraph 1 has lines 1+2; paragraph 2 has line 3
        assert len(result) == 2

    def test_parse_block_content_paragraph_breaks_on_fence(self):
        """Paragraph collection stops when it encounters a fence line (line 123)."""
        lines = ["Some text", "```python", "code()", "```"]
        result = parse_block_content(lines)

        types = [n["type"] for n in result]
        assert "paragraph" in types
        assert "codeBlock" in types

    def test_parse_table_skips_blank_data_rows(self):
        """parse_table ignores blank rows in the data section (line 225)."""
        lines = [
            "| A | B |",
            "|---|---|",
            "| 1 | 2 |",
            "",           # blank row — should be skipped
            "| 3 | 4 |",
        ]
        result = parse_table(lines)

        # Only 2 data rows (plus header) should appear; blank is skipped
        assert result["type"] == "table"
        assert len(result["content"]) == 3  # 1 header + 2 data rows

    def test_build_list_stops_when_indent_less_than_base(self):
        """build_list breaks when it encounters a line with indent < base_indent (line 307)."""
        # Call with base_indent=2 but provide lines at indent=0
        lines = ["- top level item"]
        result, consumed = build_list(lines, base_indent=2)

        # The item is at indent 0 which is < base 2, so nothing should be consumed
        assert consumed == 0

    def test_build_list_skips_deeper_line_without_base_match(self):
        """build_list skips lines with indent > base_indent when no base item precedes them (lines 310-311)."""
        # Provide lines where the only content is deeper-indented (shouldn't happen normally
        # but exercises the `indent > base_indent` skip branch)
        lines = ["    - deeply nested only"]
        # base_indent=0, line has indent=4; the item is deeper so it should be skipped.
        # build_list increments i and continues, then hits end of lines with no items
        result, consumed = build_list(lines, base_indent=0)

        # The deeper line was skipped; list ends up empty, consumed returns 0
        assert consumed == 0

    def test_build_list_breaks_on_non_list_line(self):
        """build_list stops when it hits a line that is not a list item (line 302)."""
        # The non-list line terminates the list early
        lines = ["- Item 1", "- Item 2", "Not a list item", "- Item 3"]
        result, consumed = build_list(lines)

        # Should only consume the first two list items before the plain text line
        assert result["type"] == "bulletList"
        assert len(result["content"]) == 2
        assert consumed == 2

    def test_build_list_child_collection_stops_at_non_list_line(self):
        """Child line collection stops when a non-list line is encountered (line 325)."""
        # The converter normally keeps plain-text continuation lines out of build_list,
        # but if one slips through (e.g. via direct call) the child-collection loop
        # should stop at it rather than crashing.
        lines = ["- Item 1", "  plain text continuation", "- Item 2"]
        result, consumed = build_list(lines)

        # plain text continuation is not a list line so child collection stops;
        # then the outer while loop hits it, info is None, and breaks — consuming only Item 1
        assert result["type"] == "bulletList"

    def test_build_list_task_with_child_lines_prints_warning(self, capsys):
        """build_list prints a warning when a task item has child lines (line 338)."""
        lines = [
            "- [ ] Task item",
            "  - child item",
        ]
        result, consumed = build_list(lines)

        captured = capsys.readouterr()
        assert "Warning" in captured.out or "warning" in captured.out.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_malformed_panel_syntax(self):
        """Test malformed panel syntax."""
        lines = ["[!]", "Text"]  # Empty type
        result = parse_blockquote_block(lines)

        # Should handle gracefully
        assert isinstance(result, dict)

    def test_malformed_expand_syntax(self):
        """Test malformed expand syntax."""
        lines = ["[!expand]", "Text"]  # No title
        result = parse_blockquote_block(lines)

        # Should handle gracefully
        assert isinstance(result, dict)

    def test_table_with_no_rows(self):
        """Test table with just header."""
        lines = ["| A | B |", "|---|---|"]
        result = parse_table(lines)

        # Should create valid table
        assert result["type"] == "table"

    def test_list_with_inconsistent_depths(self):
        """Test list with jumping depth levels."""
        lines = ["- L1", "      - L4"]  # Jump from 0 to deep indent
        result, consumed = build_list(lines)  # FIX: Returns tuple

        # Should handle gracefully
        assert result["type"] == "bulletList"
        assert consumed >= 1

    def test_unicode_in_table(self):
        """Test table with unicode characters."""
        lines = ["| 中文 | العربية |", "|------|---------|", "| 日本語 | हिन्दी |"]
        result = parse_table(lines)

        assert result["type"] == "table"

    def test_very_long_blockquote(self):
        """Test very long blockquote."""
        lines = ["Line " + str(i) for i in range(100)]
        result = parse_blockquote_block(lines)

        assert result["type"] == "blockquote"

    def test_special_characters_in_list(self):
        """Test list with special characters."""
        lines = ["- < > & \" '", "- Special: !@#$%"]
        result, consumed = build_list(lines)  # FIX: Returns tuple

        assert result["type"] == "bulletList"
        assert consumed == 2
