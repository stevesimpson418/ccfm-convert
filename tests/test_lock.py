"""Tests for state.lock module."""

from unittest.mock import Mock, patch

import pytest
import requests

from ccfm_convert.state.lock import (
    LOCK_PROPERTY_KEY,
    LockError,
    LockManager,
    _default_owner,
)


@pytest.fixture
def api():
    return Mock()


@pytest.fixture
def lock_mgr(api):
    return LockManager(api, "mgmt-page-123")


class TestDefaultOwner:
    @patch("ccfm_convert.state.lock.socket.gethostname", return_value="myhost")
    @patch.dict("os.environ", {"USER": "alice"}, clear=False)
    def test_returns_user_at_hostname(self, mock_hostname):
        assert _default_owner() == "alice@myhost"

    @patch("ccfm_convert.state.lock.socket.gethostname", return_value="myhost")
    @patch.dict("os.environ", {"USER": "", "USERNAME": "bob"}, clear=False)
    def test_falls_back_to_username_env(self, mock_hostname):
        assert _default_owner() == "bob@myhost"

    @patch("ccfm_convert.state.lock.socket.gethostname", return_value="myhost")
    @patch.dict("os.environ", {"USER": "", "USERNAME": ""}, clear=False)
    def test_falls_back_to_unknown(self, mock_hostname):
        assert _default_owner() == "unknown@myhost"


class TestLockStatus:
    def test_status_returns_unlocked_when_no_property(self, lock_mgr, api):
        """Returns unlocked LockInfo when property doesn't exist."""
        api.get_content_property.return_value = None

        info = lock_mgr.status()

        assert info.locked is False
        assert info.owner == ""
        api.get_content_property.assert_called_once_with("mgmt-page-123", LOCK_PROPERTY_KEY)

    def test_status_returns_lock_info_when_locked(self, lock_mgr, api):
        """Returns full LockInfo when lock property exists."""
        api.get_content_property.return_value = {
            "value": {
                "locked": True,
                "owner": "alice@host",
                "lock_id": "ci-123",
                "locked_at": "2024-01-01T00:00:00+00:00",
                "operation": "deploy",
            },
            "version": {"number": 3},
        }

        info = lock_mgr.status()

        assert info.locked is True
        assert info.owner == "alice@host"
        assert info.lock_id == "ci-123"
        assert info.locked_at == "2024-01-01T00:00:00+00:00"
        assert info.operation == "deploy"
        assert info.version == 3

    def test_status_handles_missing_fields_gracefully(self, lock_mgr, api):
        """Handles partial lock data without errors."""
        api.get_content_property.return_value = {
            "value": {"locked": True},
            "version": {"number": 1},
        }

        info = lock_mgr.status()

        assert info.locked is True
        assert info.owner == ""
        assert info.lock_id == ""


class TestLockAcquire:
    @patch("ccfm_convert.state.lock._default_owner", return_value="test@host")
    def test_acquire_succeeds_when_unlocked_no_prior_version(self, mock_owner, lock_mgr, api):
        """Acquire creates property when no prior lock exists."""
        api.get_content_property.return_value = None

        lock_mgr.acquire(operation="deploy", lock_id="ci-42")

        api.set_content_property.assert_called_once()
        call_args = api.set_content_property.call_args
        assert call_args[0][0] == "mgmt-page-123"
        assert call_args[0][1] == LOCK_PROPERTY_KEY
        value = call_args[0][2]
        assert value["locked"] is True
        assert value["owner"] == "test@host"
        assert value["lock_id"] == "ci-42"
        assert value["operation"] == "deploy"
        # No prior version → version=None
        assert call_args[1]["version"] is None

    @patch("ccfm_convert.state.lock._default_owner", return_value="test@host")
    def test_acquire_succeeds_with_prior_unlocked_version(self, mock_owner, lock_mgr, api):
        """Acquire uses version+1 when prior property exists but is unlocked."""
        api.get_content_property.return_value = {
            "value": {"locked": False},
            "version": {"number": 5},
        }

        lock_mgr.acquire()

        call_args = api.set_content_property.call_args
        assert call_args[1]["version"] == 6

    def test_acquire_raises_when_already_locked(self, lock_mgr, api):
        """Raises LockError when lock is held by another process."""
        api.get_content_property.return_value = {
            "value": {
                "locked": True,
                "owner": "other@host",
                "lock_id": "",
                "locked_at": "2024-01-01T00:00:00+00:00",
                "operation": "deploy",
            },
            "version": {"number": 2},
        }

        with pytest.raises(LockError, match="locked by other@host"):
            lock_mgr.acquire()

        api.set_content_property.assert_not_called()

    def test_acquire_raises_when_locked_with_lock_id(self, lock_mgr, api):
        """LockError message includes lock_id when present."""
        api.get_content_property.return_value = {
            "value": {
                "locked": True,
                "owner": "ci@runner",
                "lock_id": "pipeline-99",
                "locked_at": "2024-06-01T00:00:00+00:00",
                "operation": "deploy",
            },
            "version": {"number": 1},
        }

        with pytest.raises(LockError, match="pipeline-99"):
            lock_mgr.acquire()

    @patch("ccfm_convert.state.lock._default_owner", return_value="test@host")
    def test_acquire_raises_on_409_conflict(self, mock_owner, lock_mgr, api):
        """409 Conflict from Confluence is converted to LockError."""
        api.get_content_property.return_value = None

        mock_response = Mock()
        mock_response.status_code = 409
        http_error = requests.HTTPError(response=mock_response)
        api.set_content_property.side_effect = http_error

        with pytest.raises(LockError, match="version conflict"):
            lock_mgr.acquire()

    @patch("ccfm_convert.state.lock._default_owner", return_value="test@host")
    def test_acquire_propagates_non_409_http_errors(self, mock_owner, lock_mgr, api):
        """Non-409 HTTP errors are re-raised as-is."""
        api.get_content_property.return_value = None

        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.HTTPError(response=mock_response)
        api.set_content_property.side_effect = http_error

        with pytest.raises(requests.HTTPError):
            lock_mgr.acquire()

    @patch("ccfm_convert.state.lock._default_owner", return_value="test@host")
    def test_acquire_defaults_lock_id_to_empty(self, mock_owner, lock_mgr, api):
        """lock_id defaults to empty string when not provided."""
        api.get_content_property.return_value = None

        lock_mgr.acquire()

        value = api.set_content_property.call_args[0][2]
        assert value["lock_id"] == ""


class TestLockRelease:
    def test_release_deletes_lock_property_when_it_exists(self, lock_mgr, api):
        """DELETE is called when the property exists."""
        api.get_content_property.return_value = {
            "value": {"locked": True, "owner": "x@h"},
            "version": {"number": 1},
        }

        lock_mgr.release()

        api.delete_content_property.assert_called_once_with("mgmt-page-123", LOCK_PROPERTY_KEY)

    def test_release_is_noop_when_property_absent(self, lock_mgr, api):
        """No DELETE when property has never been created (Confluence 403 guard)."""
        api.get_content_property.return_value = None

        lock_mgr.release()

        api.delete_content_property.assert_not_called()

    def test_force_release_deletes_when_property_exists(self, lock_mgr, api):
        """force_release delegates to release, which DELETEs when property exists."""
        api.get_content_property.return_value = {
            "value": {"locked": True, "owner": "x@h"},
            "version": {"number": 2},
        }

        lock_mgr.force_release()

        api.delete_content_property.assert_called_once_with("mgmt-page-123", LOCK_PROPERTY_KEY)

    def test_force_release_is_noop_when_property_absent(self, lock_mgr, api):
        """force_release is a no-op when property doesn't exist."""
        api.get_content_property.return_value = None

        lock_mgr.force_release()

        api.delete_content_property.assert_not_called()
