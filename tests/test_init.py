"""Tests for state.init module."""

from unittest.mock import Mock

import pytest

from ccfm_convert.state.init import (
    CONTAINER_PAGE_TITLE,
    MANAGEMENT_PAGE_LABEL,
    MANAGEMENT_PAGE_TITLE,
    init_remote_state,
)


@pytest.fixture
def api():
    api = Mock()
    api.get_space_id.return_value = "space-123"
    api.find_page_by_title.return_value = None
    api.find_child_page_by_title.return_value = None
    api.create_page.return_value = "new-page-id"
    api.add_labels.return_value = None
    return api


class TestInitRemoteState:
    def test_creates_container_and_management_page(self, api):
        """Creates _ccfm container + CCFM State Management page when nothing exists."""
        api.create_page.side_effect = ["container-id", "mgmt-id"]

        result = init_remote_state(api, "DOCS", "space-123")

        assert result == "mgmt-id"
        assert api.create_page.call_count == 2

        # First call creates container page
        first_call = api.create_page.call_args_list[0]
        assert first_call[0][0] == "space-123"  # space_id
        assert first_call[0][1] is None  # parent_id (space root)
        assert first_call[0][2] == CONTAINER_PAGE_TITLE

        # Second call creates management page under container
        second_call = api.create_page.call_args_list[1]
        assert second_call[0][1] == "container-id"  # parent_id
        assert second_call[0][2] == MANAGEMENT_PAGE_TITLE

        # Label added to management page
        api.add_labels.assert_called_once_with("mgmt-id", [MANAGEMENT_PAGE_LABEL])

    def test_returns_existing_page_when_fully_initialized(self, api):
        """Returns existing management page ID without creating anything when both pages exist."""
        api.find_page_by_title.return_value = "existing-container-id"
        api.find_child_page_by_title.return_value = "existing-mgmt-id"

        result = init_remote_state(api, "DOCS", "space-123")

        assert result == "existing-mgmt-id"
        api.create_page.assert_not_called()
        api.add_labels.assert_not_called()

    def test_recreates_container_when_management_page_exists_but_container_missing(self, api):
        """Recreates _ccfm container when it was deleted; management page becomes visible.

        When the container was deleted but the management page survived (Confluence
        cascade delete is not guaranteed), init must always recreate the container.
        The management page won't be found via child-page lookup (it's orphaned),
        so a fresh management page is created under the new container.
        """
        api.find_page_by_title.return_value = None  # container was deleted
        api.find_child_page_by_title.return_value = None  # orphaned page not found as child
        api.create_page.side_effect = ["new-container-id", "new-mgmt-id"]

        result = init_remote_state(api, "DOCS", "space-123")

        assert result == "new-mgmt-id"
        # Both container and management page must be recreated
        assert api.create_page.call_count == 2

    def test_reuses_existing_container_page(self, api):
        """If _ccfm container exists but management page doesn't, only creates management page."""
        api.find_page_by_title.return_value = "existing-container-id"
        api.find_child_page_by_title.return_value = None
        api.create_page.return_value = "new-mgmt-id"

        result = init_remote_state(api, "DOCS", "space-123")

        assert result == "new-mgmt-id"
        # Only one create_page call (management page, not container)
        api.create_page.assert_called_once()
        call_args = api.create_page.call_args
        assert call_args[0][1] == "existing-container-id"  # parent is existing container
        assert call_args[0][2] == MANAGEMENT_PAGE_TITLE

    def test_find_child_page_by_title_called_with_correct_args(self, api):
        """Passes container_id and MANAGEMENT_PAGE_TITLE to find_child_page_by_title."""
        api.find_page_by_title.return_value = "existing-container-id"
        api.find_child_page_by_title.return_value = "existing-mgmt-id"

        init_remote_state(api, "MYSPACE", "space-456")

        api.find_child_page_by_title.assert_called_once_with(
            "existing-container-id", MANAGEMENT_PAGE_TITLE
        )

    def test_container_checked_before_management_page(self, api):
        """Container existence is checked before management page lookup."""
        api.find_page_by_title.return_value = "existing-container-id"
        api.find_child_page_by_title.return_value = "existing-mgmt-id"

        init_remote_state(api, "DOCS", "space-123")

        # Verify call order: find_page_by_title (container) then find_child_page_by_title (mgmt)
        title_idx = [c[0] for c in api.method_calls].index("find_page_by_title")
        child_idx = [c[0] for c in api.method_calls].index("find_child_page_by_title")
        assert title_idx < child_idx
