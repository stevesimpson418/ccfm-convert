"""Confluence Cloud REST API v2 Client."""

import json

import requests

# Default timeout (seconds) for all Confluence API calls.
# Prevents CI jobs hanging indefinitely when the API is slow or unresponsive.
REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 60  # File uploads may be slower for large attachments


class ConfluenceAPI:
    """Wrapper for Confluence Cloud REST API v2."""

    def __init__(self, domain, email, token):
        self.domain = domain
        self.email = email
        self.token = token
        self.base_url = f"https://{domain}/wiki/api/v2"
        self.auth = (email, token)

    def get_space_id(self, space_key):
        """Get space ID from space key."""
        url = f"{self.base_url}/spaces"
        params = {"keys": space_key}

        response = requests.get(
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

        response = requests.get(
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

        response = requests.get(
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

        response = requests.post(
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
        response = requests.get(
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

        response = requests.put(
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

        response = requests.post(
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

        response = requests.get(
            url,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            print(f"   ⚠ Warning: Could not fetch fileId for attachment {attachment_id}")
            return None

        return response.json().get("fileId")

    def upload_attachment(self, page_id, filepath, alt_text=None):
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

        # Check if attachment already exists
        response = requests.get(
            url,
            params={"filename": filepath.name},
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
            files = {"file": (filepath.name, fh)}
            response = requests.post(
                upload_url,
                files=files,
                auth=self.auth,
                headers=headers,
                timeout=UPLOAD_TIMEOUT,
            )

        if response.status_code not in [200, 201]:
            print(f"   ⚠ Warning: Could not upload {filepath.name} (status {response.status_code})")
            return None

        result = response.json()

        # The update endpoint (POST .../data) returns a single attachment object, not a
        # {"results": [...]} container like the create endpoint does. Normalise to the
        # same shape so callers can always do result["results"][0]["id"].
        if existing_attachment_id and "results" not in result:
            attachment_obj = result if "id" in result else {"id": existing_attachment_id}
            return {"results": [attachment_obj]}

        return result
