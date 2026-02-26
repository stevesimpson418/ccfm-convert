"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_confluence_api():
    """Create mock Confluence API for testing."""
    api = Mock()
    api.domain = "example.atlassian.net"
    api.email = "test@example.com"
    api.token = "test-token"
    api.base_url = "https://example.atlassian.net/wiki/api/v2"
    api.auth = ("test@example.com", "test-token")

    # Default mock responses
    api.get_space_id = Mock(return_value="space123")
    api.find_page_by_title = Mock(return_value=None)
    api.create_page = Mock(return_value="page123")
    api.update_page = Mock(return_value=None)
    api.add_labels = Mock(return_value=None)
    api.upload_attachment = Mock(return_value={"results": [{"id": "att123"}]})
    api.get_attachment_fileid = Mock(return_value="file-uuid-123")

    return api


@pytest.fixture
def sample_markdown_file(temp_dir):
    """Create a sample markdown file for testing."""
    filepath = temp_dir / "sample.md"
    content = """---
title: Sample Page
author: Test User
labels:
  - test
  - sample
---
# Sample Page

This is a sample markdown file for testing.

## Section 1

Some **bold** and *italic* text.

## Section 2

- Bullet point 1
- Bullet point 2

```python
def hello():
    print("Hello, World!")
```
"""
    filepath.write_text(content)
    return filepath


@pytest.fixture
def sample_docs_structure(temp_dir):
    """Create sample documentation structure."""
    docs_root = temp_dir / "docs"
    docs_root.mkdir()

    # Root level file
    root_file = docs_root / "index.md"
    root_file.write_text("# Index\n\nRoot level page.")

    # Subdirectory with pages
    team_dir = docs_root / "Team"
    team_dir.mkdir()

    team_file = team_dir / "overview.md"
    team_file.write_text("# Team Overview\n\nTeam information.")

    # Nested subdirectory
    engineering_dir = team_dir / "Engineering"
    engineering_dir.mkdir()

    eng_file = engineering_dir / "guide.md"
    eng_file.write_text("# Engineering Guide\n\nEngineering documentation.")

    # .page_content.md file
    page_content = team_dir / ".page_content.md"
    page_content.write_text("""---
title: Team
---
# Team

Container page for team content.""")

    return docs_root


@pytest.fixture
def sample_adf_document():
    """Create sample ADF document."""
    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": "Test Heading"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": "Test paragraph."}]},
        ],
    }


@pytest.fixture
def mock_http_response():
    """Create mock HTTP response."""

    def _create_response(status_code=200, json_data=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.raise_for_status = Mock()
        if status_code >= 400:
            response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return response

    return _create_response


@pytest.fixture
def sample_attachment_file(temp_dir):
    """Create sample attachment file."""
    filepath = temp_dir / "test_image.png"
    filepath.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header
    return filepath


# Configure pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# Auto-use fixtures for all tests
@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks between tests."""
    yield
    # Cleanup happens automatically with pytest


# Helpers for assertions
class Helpers:
    """Helper methods for tests."""

    @staticmethod
    def assert_adf_structure(adf_doc):
        """Assert basic ADF structure is valid."""
        assert "version" in adf_doc
        assert "type" in adf_doc
        assert adf_doc["type"] == "doc"
        assert "content" in adf_doc
        assert isinstance(adf_doc["content"], list)

    @staticmethod
    def assert_has_node_type(adf_doc, node_type):
        """Assert ADF document contains node of given type."""

        def find_node(content):
            for node in content:
                if isinstance(node, dict):
                    if node.get("type") == node_type:
                        return True
                    if "content" in node:
                        if find_node(node["content"]):
                            return True
            return False

        assert find_node(adf_doc["content"]), f"Node type '{node_type}' not found"

    @staticmethod
    def extract_text(adf_node):
        """Extract all text from ADF node."""
        text = []

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    text.append(node.get("text", ""))
                if "content" in node:
                    walk(node["content"])
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(adf_node)
        return " ".join(text)


@pytest.fixture
def helpers():
    """Provide helper methods to tests."""
    return Helpers()
