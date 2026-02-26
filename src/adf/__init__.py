"""
CCFM to ADF Converter Package
==============================
Confluence Cloud Flavoured Markdown to Atlassian Document Format.

A modular package for converting markdown to ADF for use with
the Confluence Cloud API.

Main entry point:
    from adf import convert

    markdown = "# Hello World\\n\\nThis is **bold** text."
    adf_doc = convert(markdown)

Modules:
    - nodes: ADF node constructors (paragraph, heading, table, etc.)
    - inline: Inline markdown parsing (bold, italic, links, etc.)
    - blocks: Block markdown parsing (tables, lists, blockquotes)
    - converter: Main conversion orchestration

Version: 2.0.0 (Refactored)
"""

# Relative imports - standard Python practice for packages
from .converter import convert, convert_markdown_to_adf

__version__ = "2.0.0"
__all__ = ["convert", "convert_markdown_to_adf"]
