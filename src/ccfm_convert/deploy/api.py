"""Confluence Cloud REST API v2 Client."""

import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Default timeout (seconds) for all Confluence API calls.
# Prevents CI jobs hanging indefinitely when the API is slow or unresponsive.
REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 60  # File uploads may be slower for large attachments

# Retry configuration for transient network errors and server-side rate limiting.
# POST is intentionally excluded: create_page and other POSTs are non-idempotent
# and retrying on 5xx would silently create duplicate pages.
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS"],
    raise_on_status=False,
)


class ConfluenceAPI:
    """Wrapper for Confluence Cloud REST API v2."""

    def __init__(self, domain, email, token):
        self.domain = domain
        self.email = email
        self.token = token
        self.base_url = f"https://{domain}/wiki/api/v2"
        self.auth = (email, token)
        adapter = HTTPAdapter(max_retries=_RETRY_STRATEGY)
        self._session = requests.Session()
        self._session.mount("https://", adapter)

    def get_space_id(self, space_key):
        """Get space ID from space key."""
        url = f"{self.base_url}/spaces"
        params = {"keys": space_key}

        response = self._session.get(
            url,
            params=params,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        results = response.json().get("results", [])
        if not results:
            raise ValueError(f"Space '{space_key}' not found")

        return results[0]["id"]

    def find_page_by_title(self, space_id, title):
        """
        Find page by title in space.

        Returns:
            Page ID if found, None otherwise
        """
        url = f"{self.base_url}/pages"
        params = {"space-id": space_id, "title": title, "limit": 1}

        response = self._session.get(
            url,
            params=params,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        results = response.json().get("results", [])
        if results:
            return results[0]["id"]
        return None

    def find_page_webui_url(self, space_id, title):
        """
        Find page by title and return its full canonical webui URL.

        Extracts _links.webui from the v2 API response, which includes the
        space key and title slug required by Confluence's XML serializer.

        Returns:
            Full https URL (e.g. https://domain/wiki/spaces/KEY/pages/ID/Title+Slug)
            or None if the page is not found.
        """
        url = f"{self.base_url}/pages"
        params = {"space-id": space_id, "title": title, "limit": 1}

        response = self._session.get(
            url,
            params=params,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        results = response.json().get("results", [])
        if results:
            webui = results[0].get("_links", {}).get("webui", "")
            if webui:
                return f"https://{self.domain}{webui}"
        return None

    def create_page(self, space_id, parent_id, title, body, status="current"):
        """Create a new page."""
        url = f"{self.base_url}/pages"

        data = {
            "spaceId": space_id,
            "status": status,
            "title": title,
            "body": {
                "representation": "atlas_doc_format",
                "value": json.dumps(body),
            },
        }

        if parent_id:
            data["parentId"] = parent_id

        response = self._session.post(
            url,
            json=data,
            auth=self.auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            print(f"\n❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            try:
                error_detail = response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
            except (ValueError, TypeError):
                pass

        response.raise_for_status()

        return response.json()["id"]

    def update_page(self, page_id, title, body, status="current"):
        """Update an existing page."""
        # Get current version
        url = f"{self.base_url}/pages/{page_id}"
        response = self._session.get(
            url,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        current_version = response.json()["version"]["number"]

        # Update page
        update_url = f"{self.base_url}/pages/{page_id}"
        data = {
            "id": page_id,
            "status": status,
            "title": title,
            "body": {
                "representation": "atlas_doc_format",
                "value": json.dumps(body),
            },
            "version": {
                "number": current_version + 1,
            },
        }

        response = self._session.put(
            update_url,
            json=data,
            auth=self.auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        return page_id

    def add_labels(self, page_id, labels):
        """Add labels to a page using v1 API."""
        if not labels:
            return

        # v1 API for labels
        url = f"https://{self.domain}/wiki/rest/api/content/{page_id}/label"

        # Always add 'managed-by-ci' label
        all_labels = list(labels) if isinstance(labels, list) else [labels]
        if "managed-by-ci" not in all_labels:
            all_labels.append("managed-by-ci")

        label_data = [{"prefix": "global", "name": label} for label in all_labels]

        response = self._session.post(
            url,
            json=label_data,
            auth=self.auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        # Labels endpoint may return 200 or 400 if label already exists
        if response.status_code not in [200, 400]:
            print(f"   ⚠ Warning: Could not add labels (status {response.status_code})")

    def get_attachment_fileid(self, attachment_id):
        """
        Get Media Services fileId for an attachment.

        CONFLUENCE API LIMITATION:
        The v1 attachment upload API does not return the Media Services fileId
        required for ADF media nodes. We must make a separate v2 GET call to
        retrieve it.

        Args:
            attachment_id: Attachment ID from v1 upload response

        Returns:
            fileId (UUID string) for use in ADF media nodes, or None if not found
        """
        url = f"{self.base_url}/attachments/{attachment_id}"

        response = self._session.get(
            url,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            print(f"   ⚠ Warning: Could not fetch fileId for attachment {attachment_id}")
            return None

        return response.json().get("fileId")

    def get_page_body(self, page_id):
        """Fetch the ADF body for a page.

        Returns:
            Parsed ADF document dict.
        """
        url = f"{self.base_url}/pages/{page_id}"
        params = {"body-format": "atlas_doc_format"}
        response = self._session.get(
            url,
            params=params,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        adf_value = data["body"]["atlas_doc_format"]["value"]
        return json.loads(adf_value)

    def delete_page(self, page_id):
        """Permanently delete a page (moves it to the site trash).

        Used by archive_page() to remove orphaned pages whose source files
        have been deleted. The v2 DELETE endpoint is the only reliable way to
        deactivate a page in Confluence Cloud — the PUT endpoint does not accept
        ``status: archived``.

        Args:
            page_id: ID of the page to delete.

        Raises:
            requests.HTTPError: if the API returns a non-2xx response.
        """
        url = f"{self.base_url}/pages/{page_id}"
        response = self._session.delete(
            url,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

    # ------------------------------------------------------------------
    # Content properties (v1 API) — used for state locking
    # ------------------------------------------------------------------

    def get_content_property(self, page_id, key):
        """Get a content property by key.

        Returns:
            Property dict (contains 'value' and 'version') or None if not found.
        """
        url = f"https://{self.domain}/wiki/rest/api/content/{page_id}/property/{key}"
        response = self._session.get(
            url,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def set_content_property(self, page_id, key, value, version=None):
        """Create or update a content property.

        When version is None, creates (POST). When version is provided, updates
        (PUT) with optimistic concurrency — Confluence returns 409 if the version
        has been changed by another process.
        """
        url = f"https://{self.domain}/wiki/rest/api/content/{page_id}/property/{key}"
        data = {"key": key, "value": value}
        if version is not None:
            data["version"] = {"number": version, "minorEdit": True}
            response = self._session.put(
                url,
                json=data,
                auth=self.auth,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
        else:
            response = self._session.post(
                url,
                json=data,
                auth=self.auth,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
        response.raise_for_status()

    def delete_content_property(self, page_id, key):
        """Delete a content property. No-op if already absent."""
        url = f"https://{self.domain}/wiki/rest/api/content/{page_id}/property/{key}"
        response = self._session.delete(
            url,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    # ------------------------------------------------------------------
    # Attachment download (v1 API) — used for remote state
    # ------------------------------------------------------------------

    def download_attachment(self, page_id, filename):
        """Download an attachment's content by filename.

        Returns:
            Raw bytes of the attachment, or None if not found.
        """
        list_url = f"https://{self.domain}/wiki/rest/api/content/{page_id}/child/attachment"
        resp = self._session.get(
            list_url,
            params={"filename": filename},
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        download_path = results[0]["_links"]["download"]
        download_url = f"https://{self.domain}/wiki{download_path}"
        resp = self._session.get(download_url, auth=self.auth, timeout=UPLOAD_TIMEOUT)
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------
    # Page discovery by parent/child (v2 API) — used to find management page
    # ------------------------------------------------------------------

    def find_child_page_by_title(self, parent_id: str, title: str) -> str | None:
        """Find a direct child page of parent_id by exact title.

        Paginates through children if needed (cursor-based). Returns the first
        match, or None if no child with that title exists.

        Returns:
            Page ID if found, None otherwise.
        """
        url = f"{self.base_url}/pages/{parent_id}/children"
        params: dict = {"limit": 50}
        while True:
            response = self._session.get(
                url,
                params=params,
                auth=self.auth,
                headers={"Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            for page in data.get("results", []):
                if page.get("title") == title:
                    return page["id"]
            next_url = data.get("_links", {}).get("next")
            if not next_url:
                break
            # next_url is a relative path; prepend the base wiki URL
            url = f"https://{self.domain}/wiki{next_url}"
            params = {}
        return None

    # ------------------------------------------------------------------
    # Page discovery by label (v1 API) — retained for external tooling
    # ------------------------------------------------------------------

    def find_page_by_label(self, space_key, label):
        """Find a page by label in a space.

        Returns:
            Page ID if found, None otherwise.
        """
        url = f"https://{self.domain}/wiki/rest/api/content"
        params = {"type": "page", "spaceKey": space_key, "label": label, "limit": 1}
        response = self._session.get(
            url,
            params=params,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None
        return results[0]["id"]

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def upload_attachment(self, page_id, filepath, alt_text=None, name=None):
        """
        Upload attachment to page using v1 API.

        CONFLUENCE API LIMITATION:
        v2 API does not have a POST endpoint for attachments yet (CONFCLOUD-77196).
        We must use the v1 API for uploading, which returns attachment metadata
        but NOT the Media Services fileId needed for ADF.

        Returns:
            Dict with v1 attachment response (contains 'id' but not 'fileId')
        """
        url = f"https://{self.domain}/wiki/rest/api/content/{page_id}/child/attachment"
        attachment_name = name or filepath.name

        # Check if attachment already exists
        response = self._session.get(
            url,
            params={"filename": attachment_name},
            auth=self.auth,
            timeout=REQUEST_TIMEOUT,
        )

        headers = {"X-Atlassian-Token": "nocheck"}

        existing_attachment_id = None
        if response.status_code == 200 and response.json().get("results"):
            # Update existing attachment
            existing_attachment_id = response.json()["results"][0]["id"]
            upload_url = f"{url}/{existing_attachment_id}/data"
            print(f"   ℹ Attachment already exists (ID: {existing_attachment_id}), updating...")
        else:
            # Create new attachment
            upload_url = url

        with open(filepath, "rb") as fh:
            files = {"file": (attachment_name, fh)}
            response = self._session.post(
                upload_url,
                files=files,
                auth=self.auth,
                headers=headers,
                timeout=UPLOAD_TIMEOUT,
            )

        if response.status_code not in [200, 201]:
            print(
                f"   ⚠ Warning: Could not upload {attachment_name} (status {response.status_code})"
            )
            return None

        result = response.json()

        # The update endpoint (POST .../data) returns a single attachment object, not a
        # {"results": [...]} container like the create endpoint does. Normalise to the
        # same shape so callers can always do result["results"][0]["id"].
        if existing_attachment_id and "results" not in result:
            attachment_obj = result if "id" in result else {"id": existing_attachment_id}
            return {"results": [attachment_obj]}

        return result
