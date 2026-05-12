"""Initialize CCFM remote state infrastructure in a Confluence space."""

from ccfm_convert.deploy.api import ConfluenceAPI

CONTAINER_PAGE_TITLE = "_ccfm"
MANAGEMENT_PAGE_TITLE = "CCFM State Management"
MANAGEMENT_PAGE_LABEL = "ccfm-internal"

_MANAGEMENT_PAGE_ADF = {
    "version": 1,
    "type": "doc",
    "content": [
        {
            "type": "panel",
            "attrs": {"panelType": "info"},
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "This page is managed by ccfm-convert. "
                            "It stores deployment state (ccfm-page-* content properties) "
                            "and locking metadata (ccfm-lock content property). "
                            "Do not edit this page manually.",
                        }
                    ],
                }
            ],
        }
    ],
}


def init_remote_state(api: ConfluenceAPI, space_key: str, space_id: str) -> str:
    """Create the CCFM management infrastructure if it does not already exist.

    Creates a ``_ccfm`` container page at the space root, then a
    ``CCFM State Management`` child page with the ``ccfm-internal`` label.

    The management page is discovered as a direct child of the ``_ccfm``
    container (not by label search), so orphaned management pages left over
    from failed cleanups are automatically ignored.

    Returns:
        The page ID of the management page (new or existing).
    """
    _CONTAINER_ADF = {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "CCFM internal management pages. Do not delete.",
                    }
                ],
            }
        ],
    }

    # Always ensure the _ccfm container page exists.
    # Do this before checking for the management page so that a deleted container
    # is always recreated, even when the management page survived as an orphan.
    container_id = api.find_page_by_title(space_id, CONTAINER_PAGE_TITLE)
    if container_id is None:
        container_id = api.create_page(space_id, None, CONTAINER_PAGE_TITLE, _CONTAINER_ADF)
        print(f"Created container page: {CONTAINER_PAGE_TITLE} (ID: {container_id})")

    # Find management page as a direct child of the container (deterministic).
    # Child-page lookup ignores orphaned management pages from failed cleanups —
    # those pages are not under the container so they won't be returned here.
    existing_id = api.find_child_page_by_title(container_id, MANAGEMENT_PAGE_TITLE)
    if existing_id is not None:
        print(f"Management page already exists (ID: {existing_id}).")
        return existing_id

    # Create management page under container
    page_id = api.create_page(space_id, container_id, MANAGEMENT_PAGE_TITLE, _MANAGEMENT_PAGE_ADF)
    api.add_labels(page_id, [MANAGEMENT_PAGE_LABEL])
    print(f"Created management page: {MANAGEMENT_PAGE_TITLE} (ID: {page_id})")
    return page_id
