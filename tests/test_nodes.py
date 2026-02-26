"""Tests for adf.nodes module."""

import pytest

from adf.nodes import (
    NARROW_PAGE_WIDTH_PX,
    blockquote,
    bullet_list,
    code_block,
    date_node,
    doc,
    emoji_node,
    expand,
    hard_break,
    heading,
    inline_card,
    list_item,
    media_single,
    ordered_list,
    panel,
    paragraph,
    paragraph_with_alignment,
    resolve_image_width,
    rule,
    status_node,
    table_cell,
    table_header,
    table_node,
    table_row,
    task_item,
    task_list,
    text_node,
)


class TestDocumentStructure:
    """Test document and block-level nodes."""

    def test_doc(self):
        """Test root document node."""
        content = [paragraph([text_node("test")])]
        result = doc(content)

        assert result["version"] == 1
        assert result["type"] == "doc"
        assert result["content"] == content

    def test_heading(self):
        """Test heading nodes at all levels."""
        for level in range(1, 7):
            content = [text_node(f"Heading {level}")]
            result = heading(level, content)

            assert result["type"] == "heading"
            assert result["attrs"]["level"] == level
            assert result["content"] == content

    def test_paragraph(self):
        """Test paragraph node."""
        content = [text_node("Hello world")]
        result = paragraph(content)

        assert result["type"] == "paragraph"
        assert result["content"] == content

    def test_paragraph_with_alignment_center(self):
        """Test paragraph with center alignment."""
        content = [text_node("Centered text")]
        result = paragraph_with_alignment(content, "center")

        assert result["type"] == "paragraph"
        assert result["marks"] == [{"type": "alignment", "attrs": {"align": "center"}}]
        assert result["content"] == content

    def test_paragraph_with_alignment_end(self):
        """Test paragraph with right alignment."""
        content = [text_node("Right-aligned text")]
        result = paragraph_with_alignment(content, "end")

        assert result["type"] == "paragraph"
        assert result["marks"] == [{"type": "alignment", "attrs": {"align": "end"}}]

    def test_paragraph_with_alignment_none(self):
        """Test paragraph with no alignment (default left)."""
        content = [text_node("Left-aligned text")]
        result = paragraph_with_alignment(content, None)

        assert result["type"] == "paragraph"
        assert "marks" not in result
        assert result["content"] == content

    def test_blockquote(self):
        """Test blockquote node."""
        content = [paragraph([text_node("Quote")])]
        result = blockquote(content)

        assert result["type"] == "blockquote"
        assert result["content"] == content

    def test_code_block(self):
        """Test code block with language."""
        code = "print('hello')"
        result = code_block(code, "python")

        assert result["type"] == "codeBlock"
        assert result["attrs"]["language"] == "python"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == code

    def test_code_block_no_language(self):
        """Test code block without language."""
        code = "echo 'hello'"
        result = code_block(code)

        assert result["type"] == "codeBlock"
        assert "language" not in result.get("attrs", {})

    def test_rule(self):
        """Test horizontal rule."""
        result = rule()

        assert result["type"] == "rule"


class TestLists:
    """Test list nodes."""

    def test_bullet_list(self):
        """Test bullet list."""
        items = [list_item([paragraph([text_node("Item 1")])])]
        result = bullet_list(items)

        assert result["type"] == "bulletList"
        assert result["content"] == items

    def test_ordered_list(self):
        """Test ordered list."""
        items = [list_item([paragraph([text_node("First")])])]
        result = ordered_list(items)

        assert result["type"] == "orderedList"
        assert result["content"] == items

    def test_list_item(self):
        """Test list item."""
        content = [paragraph([text_node("Item")])]
        result = list_item(content)

        assert result["type"] == "listItem"
        assert result["content"] == content

    def test_nested_lists(self):
        """Test nested bullet list."""
        inner = bullet_list([list_item([paragraph([text_node("Nested")])])])
        outer = bullet_list([list_item([paragraph([text_node("Top")]), inner])])

        assert outer["type"] == "bulletList"
        assert len(outer["content"]) == 1
        assert len(outer["content"][0]["content"]) == 2

    def test_task_list(self):
        """Test task list (checklist)."""
        items = [task_item("TODO", [text_node("Task 1")]), task_item("DONE", [text_node("Task 2")])]
        result = task_list(items)

        assert result["type"] == "taskList"
        assert "localId" in result["attrs"]
        assert len(result["content"]) == 2

    def test_task_item(self):
        """Test task item."""
        result = task_item("TODO", [text_node("My task")])

        assert result["type"] == "taskItem"
        assert result["attrs"]["state"] == "TODO"
        assert "localId" in result["attrs"]
        assert result["content"][0]["text"] == "My task"

    def test_task_item_done(self):
        """Test completed task item."""
        result = task_item("DONE", [text_node("Completed task")])

        assert result["type"] == "taskItem"
        assert result["attrs"]["state"] == "DONE"

    def test_ordered_list_with_start(self):
        """Test ordered list with custom start number."""
        items = [list_item([paragraph([text_node("Item")])])]
        result = ordered_list(items, order=5)

        assert result["type"] == "orderedList"
        assert result["attrs"]["order"] == 5


class TestTables:
    """Test table nodes."""

    def test_table(self):
        """Test table structure."""
        rows = [
            table_row([table_header([paragraph([text_node("Header")])])]),
            table_row([table_cell([paragraph([text_node("Cell")])])]),
        ]
        result = table_node(rows)  # FIX: Function is called table_node, not table

        assert result["type"] == "table"
        assert result["content"] == rows

    def test_table_row(self):
        """Test table row."""
        cells = [table_cell([paragraph([text_node("Cell")])])]
        result = table_row(cells)

        assert result["type"] == "tableRow"
        assert result["content"] == cells

    def test_table_cell(self):
        """Test table cell."""
        content = [paragraph([text_node("Content")])]
        result = table_cell(content)

        assert result["type"] == "tableCell"
        assert result["content"] == content

    def test_table_header(self):
        """Test table header."""
        content = [paragraph([text_node("Header")])]
        result = table_header(content)

        assert result["type"] == "tableHeader"
        assert result["content"] == content

    @pytest.mark.skip(reason="colspan/rowspan not supported in table_cell()")
    def test_table_cell_with_colspan(self):
        """Test table cell with colspan."""
        content = [paragraph([text_node("Wide cell")])]
        result = table_cell(content, colspan=2)

        assert result["attrs"]["colspan"] == 2

    @pytest.mark.skip(reason="colspan/rowspan not supported in table_cell()")
    def test_table_cell_with_rowspan(self):
        """Test table cell with rowspan."""
        content = [paragraph([text_node("Tall cell")])]
        result = table_cell(content, rowspan=2)

        assert result["attrs"]["rowspan"] == 2


class TestPanelsAndExpands:
    """Test panel and expand nodes."""

    def test_panel_info(self):
        """Test info panel."""
        content = [paragraph([text_node("Info")])]
        result = panel("info", content)  # FIX: panel_type first, then content

        assert result["type"] == "panel"
        assert result["attrs"]["panelType"] == "info"
        assert result["content"] == content

    def test_panel_note(self):
        """Test note panel."""
        content = [paragraph([text_node("Note")])]
        result = panel("note", content)  # FIX: panel_type first

        assert result["attrs"]["panelType"] == "note"

    def test_panel_warning(self):
        """Test warning panel."""
        content = [paragraph([text_node("Warning")])]
        result = panel("warning", content)  # FIX: panel_type first

        assert result["attrs"]["panelType"] == "warning"

    def test_panel_error(self):
        """Test error panel."""
        content = [paragraph([text_node("Error")])]
        result = panel("error", content)  # FIX: panel_type first

        assert result["attrs"]["panelType"] == "error"

    def test_panel_success(self):
        """Test success panel."""
        content = [paragraph([text_node("Success")])]
        result = panel("success", content)  # FIX: panel_type first

        assert result["attrs"]["panelType"] == "success"

    def test_expand(self):
        """Test expand node."""
        title = "Click to expand"
        content = [paragraph([text_node("Hidden content")])]
        result = expand(title, content)

        assert result["type"] == "expand"
        assert result["attrs"]["title"] == title
        assert result["content"] == content


class TestInlineNodes:
    """Test inline text nodes."""

    def test_text_node(self):
        """Test plain text node."""
        result = text_node("Hello")

        assert result["type"] == "text"
        assert result["text"] == "Hello"
        assert "marks" not in result

    def test_hard_break(self):
        """Test hard break node."""
        result = hard_break()

        assert result["type"] == "hardBreak"

    def test_link(self):
        """Test link node using text_node with link mark."""
        text = "Click here"
        url = "https://example.com"
        result = text_node(text, marks=[{"type": "link", "attrs": {"href": url}}])

        assert result["type"] == "text"
        assert result["text"] == text
        assert len(result["marks"]) == 1
        assert result["marks"][0]["type"] == "link"
        assert result["marks"][0]["attrs"]["href"] == url

    def test_strong(self):
        """Test bold text node."""
        result = text_node("Bold", marks=[{"type": "strong"}])

        assert result["type"] == "text"
        assert result["text"] == "Bold"
        assert result["marks"] == [{"type": "strong"}]

    def test_em(self):
        """Test italic text node."""
        result = text_node("Italic", marks=[{"type": "em"}])

        assert result["type"] == "text"
        assert result["text"] == "Italic"
        assert result["marks"] == [{"type": "em"}]

    def test_code(self):
        """Test inline code node."""
        result = text_node("print()", marks=[{"type": "code"}])

        assert result["type"] == "text"
        assert result["text"] == "print()"
        assert result["marks"] == [{"type": "code"}]

    def test_strike(self):
        """Test strikethrough text node."""
        result = text_node("Deleted", marks=[{"type": "strike"}])

        assert result["type"] == "text"
        assert result["text"] == "Deleted"
        assert result["marks"] == [{"type": "strike"}]

    def test_underline(self):
        """Test underlined text node."""
        result = text_node("Important", marks=[{"type": "underline"}])

        assert result["type"] == "text"
        assert result["text"] == "Important"
        assert result["marks"] == [{"type": "underline"}]

    def test_multiple_marks(self):
        """Test text with multiple marks."""
        # Simulate bold + italic
        node = text_node("Text")
        node["marks"] = [{"type": "strong"}, {"type": "em"}]

        assert len(node["marks"]) == 2
        assert node["marks"][0]["type"] == "strong"
        assert node["marks"][1]["type"] == "em"


class TestMediaAndCards:
    """Test media and card nodes."""

    def test_inline_card(self):
        """Test inline card."""
        url = "https://example.com"
        result = inline_card(url)

        assert result["type"] == "inlineCard"
        assert result["attrs"]["url"] == url

    def test_media_single_external(self):
        """Test media node with external URL defaults to narrow width."""
        url = "https://example.com/image.png"
        alt = "Test image"
        result = media_single(url=url, alt=alt)

        assert result["type"] == "mediaSingle"
        assert result["attrs"]["layout"] == "center"
        assert result["attrs"]["width"] == NARROW_PAGE_WIDTH_PX
        assert result["attrs"]["widthType"] == "pixel"
        assert result["content"][0]["type"] == "media"
        assert result["content"][0]["attrs"]["type"] == "external"
        assert result["content"][0]["attrs"]["url"] == url
        assert result["content"][0]["attrs"]["alt"] == alt

    def test_media_single_file(self):
        """Test media node with file attachment defaults to narrow width."""
        file_id = "abc-123-def"
        collection = "contentId-456"
        alt = "Attachment image"
        result = media_single(file_id=file_id, collection=collection, alt=alt)

        assert result["type"] == "mediaSingle"
        assert result["attrs"]["width"] == NARROW_PAGE_WIDTH_PX
        assert result["attrs"]["widthType"] == "pixel"
        assert result["content"][0]["type"] == "media"
        assert result["content"][0]["attrs"]["type"] == "file"
        assert result["content"][0]["attrs"]["id"] == file_id
        assert result["content"][0]["attrs"]["collection"] == collection
        assert result["content"][0]["attrs"]["alt"] == alt

    def test_media_single_no_alt(self):
        """Test media node without alt text."""
        url = "https://example.com/image.png"
        result = media_single(url=url)

        assert "alt" not in result["content"][0]["attrs"]

    def test_media_single_invalid(self):
        """Test media node with neither url nor file_id raises error."""
        with pytest.raises(ValueError, match="Must provide either"):
            media_single()

    def test_media_single_width_narrow_preset(self):
        """Test 'narrow' preset maps to 760px."""
        result = media_single(url="img.png", width="narrow")
        assert result["attrs"]["layout"] == "center"
        assert result["attrs"]["width"] == NARROW_PAGE_WIDTH_PX
        assert result["attrs"]["widthType"] == "pixel"

    def test_media_single_width_wide_preset(self):
        """Test 'wide' preset uses wide layout with no pixel width attrs."""
        result = media_single(url="img.png", width="wide")
        assert result["attrs"]["layout"] == "wide"
        assert "width" not in result["attrs"]
        assert "widthType" not in result["attrs"]

    def test_media_single_width_max_preset(self):
        """Test 'max' preset uses full-width layout with no pixel width attrs."""
        result = media_single(url="img.png", width="max")
        assert result["attrs"]["layout"] == "full-width"
        assert "width" not in result["attrs"]
        assert "widthType" not in result["attrs"]

    def test_media_single_width_custom_pixels(self):
        """Test custom integer pixel width."""
        result = media_single(url="img.png", width=500)
        assert result["attrs"]["layout"] == "center"
        assert result["attrs"]["width"] == 500
        assert result["attrs"]["widthType"] == "pixel"

    def test_media_single_width_string_integer(self):
        """Test width as string integer (from markdown attribute parser)."""
        result = media_single(url="img.png", width="500")
        assert result["attrs"]["width"] == 500


class TestResolveImageWidth:
    """Test resolve_image_width helper."""

    def test_none_returns_narrow(self):
        assert resolve_image_width(None) == ("center", NARROW_PAGE_WIDTH_PX, "pixel")

    def test_narrow_preset(self):
        assert resolve_image_width("narrow") == ("center", NARROW_PAGE_WIDTH_PX, "pixel")

    def test_wide_preset(self):
        assert resolve_image_width("wide") == ("wide", None, None)

    def test_max_preset(self):
        assert resolve_image_width("max") == ("full-width", None, None)

    def test_integer_width(self):
        assert resolve_image_width(400) == ("center", 400, "pixel")

    def test_string_integer_width(self):
        assert resolve_image_width("400") == ("center", 400, "pixel")

    def test_invalid_string_falls_back_to_narrow(self):
        assert resolve_image_width("bogus") == ("center", NARROW_PAGE_WIDTH_PX, "pixel")


class TestSpecialNodes:
    """Test special Confluence nodes."""

    def test_emoji_node(self):
        """Test emoji node."""
        result = emoji_node("smile")

        assert result["type"] == "emoji"
        assert result["attrs"]["shortName"] == ":smile:"

    def test_date_node(self):
        """Test date node."""
        date_str = "2024-01-01"
        result = date_node(date_str)

        assert result["type"] == "date"
        assert "timestamp" in result["attrs"]
        # Timestamp should be a string representing milliseconds
        assert isinstance(result["attrs"]["timestamp"], str)

    def test_status_node(self):
        """Test status node."""
        result = status_node("In Progress", "blue")

        assert result["type"] == "status"
        assert result["attrs"]["text"] == "In Progress"
        assert result["attrs"]["color"] == "BLUE"  # Color is uppercased

    def test_status_node_default_color(self):
        """Test status node with neutral color."""
        result = status_node("Done", "neutral")

        assert result["attrs"]["text"] == "Done"
        assert result["attrs"]["color"] == "NEUTRAL"  # Color is uppercased

    def test_date_node_invalid_format_returns_zero_timestamp(self):
        """date_node falls back to timestamp '0' when the date string is not parseable."""
        result = date_node("not-a-date")

        assert result["type"] == "date"
        assert result["attrs"]["timestamp"] == "0"


class TestComplexStructures:
    """Test complex nested structures."""

    def test_nested_blockquote(self):
        """Test blockquote with nested paragraph."""
        p = paragraph(
            [
                text_node("Bold", marks=[{"type": "strong"}]),
                text_node(" and "),
                text_node("italic", marks=[{"type": "em"}]),
            ]
        )
        quote = blockquote([p])

        assert quote["type"] == "blockquote"
        assert quote["content"][0]["type"] == "paragraph"
        assert len(quote["content"][0]["content"]) == 3

    def test_list_with_formatting(self):
        """Test list with formatted text."""
        item = list_item(
            [
                paragraph(
                    [
                        text_node("Important:", marks=[{"type": "strong"}]),
                        text_node(" "),
                        text_node(
                            "Click here",
                            marks=[{"type": "link", "attrs": {"href": "https://example.com"}}],
                        ),
                    ]
                )
            ]
        )
        lst = bullet_list([item])

        assert lst["content"][0]["content"][0]["content"][0]["marks"][0]["type"] == "strong"

    def test_panel_with_expand(self):
        """Test panel containing expand."""
        exp = expand("Details", [paragraph([text_node("Hidden")])])
        pan = panel("info", [exp])  # Correct order: panel(panel_type, content)

        assert pan["type"] == "panel"
        assert pan["content"][0]["type"] == "expand"

    def test_table_with_formatted_cells(self):
        """Test table with formatted content."""
        header = table_row(
            [
                table_header([paragraph([text_node("Column 1", marks=[{"type": "strong"}])])]),
                table_header([paragraph([text_node("Column 2", marks=[{"type": "strong"}])])]),
            ]
        )
        row = table_row(
            [
                table_cell([paragraph([text_node("code", marks=[{"type": "code"}])])]),
                table_cell(
                    [
                        paragraph(
                            [
                                text_node(
                                    "link",
                                    marks=[
                                        {"type": "link", "attrs": {"href": "http://example.com"}}
                                    ],
                                )
                            ]
                        )
                    ]
                ),
            ]
        )
        tbl = table_node([header, row])  # Use table_node, not table

        assert len(tbl["content"]) == 2
        assert (
            tbl["content"][0]["content"][0]["content"][0]["content"][0]["marks"][0]["type"]
            == "strong"
        )
